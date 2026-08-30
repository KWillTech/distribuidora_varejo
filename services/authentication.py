"""Casos de uso de login, sessão e alteração de senha."""

from __future__ import annotations

from datetime import timedelta
from secrets import token_urlsafe
from uuid import uuid4

from models.auth import AuthenticatedSession, User, utc_now
from repositories.auth import AuditRepository, ProfileRepository, UserRepository
from services.rbac import effective_permissions
from services.security import PasswordService


class AuthenticationError(RuntimeError):
    """Falha de autenticação com mensagem segura para a interface."""


class AccountLockedError(AuthenticationError):
    """Conta temporariamente bloqueada."""


class AuthenticationService:
    MAX_ATTEMPTS = 5
    LOCK_MINUTES = 15

    def __init__(self, users: UserRepository, profiles: ProfileRepository, audit: AuditRepository, passwords: PasswordService | None = None) -> None:
        self._users = users
        self._profiles = profiles
        self._audit = audit
        self._passwords = passwords or PasswordService()
        self._sessions: dict[str, AuthenticatedSession] = {}

    def login(self, login: str, password: str) -> AuthenticatedSession:
        now = utc_now()
        found = self._users.find_by_login(login)
        if found is None:
            self._audit.record(user=None, action="login_falhou", module="autenticacao", details={"login": login.strip().lower()})
            raise AuthenticationError("Usuário ou senha inválidos.")
        user, password_hash = found
        if not user.active:
            self._audit.record(user=user, action="login_bloqueado_inativo", module="autenticacao")
            raise AuthenticationError("Usuário ou senha inválidos.")
        if user.locked_until and user.locked_until > now:
            self._audit.record(user=user, action="login_bloqueado_temporariamente", module="autenticacao")
            raise AccountLockedError("Conta temporariamente bloqueada. Tente novamente mais tarde.")
        if not self._passwords.verify(password_hash, password):
            attempts = user.failed_attempts + 1
            locked_until = now + timedelta(minutes=self.LOCK_MINUTES) if attempts >= self.MAX_ATTEMPTS else None
            self._users.update_login_state(user.id or "", failed_attempts=attempts, locked_until=locked_until)
            self._audit.record(user=user, action="login_falhou", module="autenticacao", details={"tentativas": attempts})
            if locked_until:
                raise AccountLockedError("Conta temporariamente bloqueada. Tente novamente mais tarde.")
            raise AuthenticationError("Usuário ou senha inválidos.")
        profile = self._profiles.get(user.profile_code)
        if profile is None:
            raise AuthenticationError("Perfil inativo ou inexistente.")
        self._users.update_login_state(user.id or "", failed_attempts=0, locked_until=None, last_access_at=now)
        user.failed_attempts = 0
        user.locked_until = None
        user.last_access_at = now
        session = AuthenticatedSession(session_id=str(uuid4()), user=user, permissions=effective_permissions(user, profile))
        self._sessions[session.session_id] = session
        self._audit.record(user=user, action="login", module="autenticacao")
        return session

    def change_own_password(self, session: AuthenticatedSession, current_password: str, new_password: str) -> None:
        found = self._users.find_by_login(session.user.username)
        if found is None or not self._passwords.verify(found[1], current_password):
            raise AuthenticationError("Senha atual inválida.")
        self._users.change_password(session.user.id or "", self._passwords.hash(new_password), False)
        session.user.must_change_password = False
        self._audit.record(user=session.user, action="senha_alterada", module="usuarios", affected_id=session.user.id)

    def logout(self, session: AuthenticatedSession) -> None:
        self._sessions.pop(session.session_id, None)
        self._audit.record(user=session.user, action="logout", module="autenticacao")

    @staticmethod
    def generate_temporary_password() -> str:
        return "Tmp!9" + token_urlsafe(12)
