"""Testes dos fluxos críticos de autenticação."""

from __future__ import annotations

from copy import deepcopy

import pytest

from models.auth import ProfileCode, User
from services.authentication import AccountLockedError, AuthenticationError, AuthenticationService
from services.rbac import default_profiles
from services.security import PasswordService


class FakeUsers:
    def __init__(self, user: User, password_hash: str) -> None:
        self.user = user
        self.password_hash = password_hash

    def find_by_login(self, login: str):
        if login.lower() not in (self.user.username, str(self.user.email).lower()):
            return None
        return deepcopy(self.user), self.password_hash

    def update_login_state(self, user_id: str, *, failed_attempts: int, locked_until, last_access_at=None) -> None:
        self.user.failed_attempts = failed_attempts
        self.user.locked_until = locked_until
        if last_access_at:
            self.user.last_access_at = last_access_at

    def change_password(self, user_id: str, password_hash: str, force_change: bool) -> None:
        self.password_hash = password_hash
        self.user.must_change_password = force_change


class FakeProfiles:
    def get(self, code):
        return next((profile for profile in default_profiles() if profile.code == code), None)


class FakeAudit:
    def __init__(self) -> None:
        self.actions: list[str] = []

    def record(self, **data) -> None:
        self.actions.append(data["action"])


@pytest.fixture
def auth_parts():
    password = "SenhaForte!123"
    user = User(id="u1", username="admin", email="admin@example.com", full_name="Administrador Principal", profile_code=ProfileCode.ADMIN)
    users = FakeUsers(user, PasswordService().hash(password))
    audit = FakeAudit()
    return AuthenticationService(users, FakeProfiles(), audit), users, audit, password


def test_successful_login_resets_failures(auth_parts) -> None:
    service, users, audit, password = auth_parts
    users.user.failed_attempts = 2
    session = service.login("ADMIN", password)
    assert users.user.failed_attempts == 0
    assert session.user.profile_code == ProfileCode.ADMIN
    assert "login" in audit.actions


def test_fifth_failure_locks_account(auth_parts) -> None:
    service, users, _, _ = auth_parts
    for _ in range(4):
        with pytest.raises(AuthenticationError):
            service.login("admin", "errada")
    with pytest.raises(AccountLockedError):
        service.login("admin", "errada")
    assert users.user.locked_until is not None


def test_inactive_user_cannot_login(auth_parts) -> None:
    service, users, _, password = auth_parts
    users.user.active = False
    with pytest.raises(AuthenticationError, match="inválidos"):
        service.login("admin", password)

