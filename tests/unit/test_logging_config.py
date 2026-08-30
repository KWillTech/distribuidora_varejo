"""Testes de proteção de dados sensíveis nos logs."""

from utils.logging_config import SensitiveDataFilter


def test_sanitize_mongodb_credentials() -> None:
    text = "Falha mongodb://admin:minha-senha@localhost:27017/banco"
    sanitized = SensitiveDataFilter.sanitize(text)

    assert sanitized == "Falha mongodb://***:***@localhost:27017/banco"
    assert "minha-senha" not in sanitized


def test_sanitize_password_field() -> None:
    sanitized = SensitiveDataFilter.sanitize("senha=segredo")

    assert sanitized == "senha=***"

