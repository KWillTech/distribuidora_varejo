"""Testes de senha Argon2 e política mínima."""

import pytest

from services.security import PasswordPolicyError, PasswordService


def test_password_is_hashed_and_verified() -> None:
    service = PasswordService()
    password_hash = service.hash("SenhaForte!123")

    assert password_hash.startswith("$argon2")
    assert "SenhaForte!123" not in password_hash
    assert service.verify(password_hash, "SenhaForte!123") is True
    assert service.verify(password_hash, "incorreta") is False


def test_weak_password_is_rejected() -> None:
    with pytest.raises(PasswordPolicyError):
        PasswordService().hash("123456")

