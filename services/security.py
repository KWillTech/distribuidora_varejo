"""Primitivas de senha e política de credenciais."""

from __future__ import annotations

import re

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError


class PasswordPolicyError(ValueError):
    """Senha não atende à política mínima."""


class PasswordService:
    """Protege senhas com Argon2id e parâmetros seguros da biblioteca."""

    def __init__(self) -> None:
        self._hasher = PasswordHasher()

    @staticmethod
    def validate(password: str) -> None:
        requirements = (
            (len(password) >= 10, "pelo menos 10 caracteres"),
            (bool(re.search(r"[A-Z]", password)), "uma letra maiúscula"),
            (bool(re.search(r"[a-z]", password)), "uma letra minúscula"),
            (bool(re.search(r"\d", password)), "um número"),
            (bool(re.search(r"[^A-Za-z0-9]", password)), "um símbolo"),
        )
        missing = [message for valid, message in requirements if not valid]
        if missing:
            raise PasswordPolicyError("A senha deve conter " + ", ".join(missing) + ".")

    def hash(self, password: str) -> str:
        self.validate(password)
        return self._hasher.hash(password)

    def verify(self, password_hash: str, password: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False

