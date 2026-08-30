"""Criação idempotente dos perfis e administrador inicial."""

from __future__ import annotations

from models.auth import ProfileCode, User, utc_now
from repositories.auth import AuditRepository, ProfileRepository, UserRepository
from services.authentication import AuthenticationService
from services.rbac import default_profiles
from services.security import PasswordService


def seed_authentication(users: UserRepository, profiles: ProfileRepository, audit: AuditRepository, initial_password: str | None = None) -> str | None:
    for profile in default_profiles():
        profiles.upsert(profile)
    if users.count() > 0:
        return None
    password = initial_password or AuthenticationService.generate_temporary_password()
    now = utc_now()
    admin = User(username="admin", email="admin@localhost.local", full_name="Administrador Principal", profile_code=ProfileCode.ADMIN, must_change_password=True, created_at=now, updated_at=now)
    created = users.create(admin, PasswordService().hash(password))
    audit.record(user=None, action="administrador_inicial_criado", module="usuarios", affected_id=created.id)
    return password
