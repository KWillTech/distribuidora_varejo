"""Casos de uso administrativos de usuários."""

from __future__ import annotations

from models.auth import AuthenticatedSession, Permission, ProfileCode, User, UserCreate
from repositories.auth import AuditRepository, UserRepository
from services.rbac import AuthorizationError, require_permission
from services.security import PasswordService


class UserService:
    def __init__(self, users: UserRepository, audit: AuditRepository, passwords: PasswordService | None = None) -> None:
        self._users = users
        self._audit = audit
        self._passwords = passwords or PasswordService()

    def list_users(self, session: AuthenticatedSession) -> list[User]:
        require_permission(session, Permission.USERS_VIEW)
        return self._users.list_all()

    def create_user(self, session: AuthenticatedSession, data: UserCreate) -> User:
        require_permission(session, Permission.USERS_CREATE)
        user = User(
            username=data.username.lower(), email=data.email, full_name=data.full_name,
            profile_code=data.profile_code, individual_grants=data.individual_grants,
            individual_denials=data.individual_denials,
        )
        created = self._users.create(user, self._passwords.hash(data.temporary_password))
        self._audit.record(user=session.user, action="usuario_criado", module="usuarios", affected_id=created.id)
        return created

    def set_active(self, session: AuthenticatedSession, user_id: str, active: bool, reason: str) -> None:
        require_permission(session, Permission.USERS_DEACTIVATE)
        target = self._users.get(user_id)
        if target is None:
            raise ValueError("Usuário não encontrado.")
        if target.id == session.user.id and not active:
            raise AuthorizationError("Não é permitido inativar o próprio usuário.")
        if target.profile_code == ProfileCode.ADMIN and target.username == "admin" and not active:
            raise AuthorizationError("O administrador principal não pode ser inativado.")
        if not reason.strip():
            raise ValueError("Informe o motivo da alteração.")
        self._users.set_active(user_id, active)
        self._audit.record(user=session.user, action="usuario_ativado" if active else "usuario_inativado", module="usuarios", affected_id=user_id, reason=reason)

    def reset_password(self, session: AuthenticatedSession, user_id: str, temporary_password: str) -> None:
        require_permission(session, Permission.USERS_RESET_PASSWORD)
        if self._users.get(user_id) is None:
            raise ValueError("Usuário não encontrado.")
        self._users.change_password(user_id, self._passwords.hash(temporary_password), True)
        self._audit.record(user=session.user, action="senha_redefinida", module="usuarios", affected_id=user_id)

    def update_permissions(self, session: AuthenticatedSession, user_id: str, grants: set[Permission], denials: set[Permission]) -> None:
        require_permission(session, Permission.PERMISSIONS_MANAGE)
        target = self._users.get(user_id)
        if target is None:
            raise ValueError("Usuário não encontrado.")
        if grants & denials:
            raise ValueError("Uma permissão não pode ser liberada e bloqueada ao mesmo tempo.")
        self._users.update_permissions(user_id, grants, denials)
        self._audit.record(user=session.user, action="permissoes_alteradas", module="usuarios", affected_id=user_id)
