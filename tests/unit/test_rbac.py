"""Testes de perfis e permissões efetivas."""

import pytest

from models.auth import AuthenticatedSession, Permission, ProfileCode, User
from services.rbac import AuthorizationError, default_profiles, effective_permissions, require_permission


def test_admin_has_every_permission() -> None:
    admin = next(profile for profile in default_profiles() if profile.code == ProfileCode.ADMIN)
    assert admin.permissions == set(Permission)


def test_individual_denial_overrides_profile() -> None:
    profile = next(profile for profile in default_profiles() if profile.code == ProfileCode.MANAGER)
    user = User(username="gerente", email="gerente@example.com", full_name="Pessoa Gerente", profile_code=ProfileCode.MANAGER, individual_denials={Permission.COST_VIEW})
    assert Permission.COST_VIEW not in effective_permissions(user, profile)


def test_service_guard_rejects_missing_permission() -> None:
    user = User(username="caixa", email="caixa@example.com", full_name="Pessoa Caixa", profile_code=ProfileCode.CASHIER)
    session = AuthenticatedSession(session_id="session", user=user, permissions={Permission.POS_ACCESS})
    with pytest.raises(AuthorizationError):
        require_permission(session, Permission.USERS_CREATE)

