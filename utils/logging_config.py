"""Configuração de logs com proteção contra exposição de credenciais."""

from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler

from config.settings import Settings


MONGO_CREDENTIALS = re.compile(r"(mongodb(?:\+srv)?://)([^@\s/]+)@", re.IGNORECASE)
PASSWORD_VALUE = re.compile(
    r"(?i)(password|senha|mongodb_uri)(\s*[=:]\s*)([^,;\s]+)"
)


class SensitiveDataFilter(logging.Filter):
    """Remove credenciais conhecidas das mensagens antes da gravação."""

    @staticmethod
    def sanitize(value: object) -> object:
        if not isinstance(value, str):
            return value
        value = MONGO_CREDENTIALS.sub(r"\1***:***@", value)
        return PASSWORD_VALUE.sub(r"\1\2***", value)

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self.sanitize(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    key: self.sanitize(value) for key, value in record.args.items()
                }
            else:
                record.args = tuple(self.sanitize(value) for value in record.args)
        return True


def configure_logging(settings: Settings) -> None:
    """Configura saída rotativa em arquivo e saída legível no console."""
    settings.app_log_dir.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )
    sensitive_filter = SensitiveDataFilter()

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console.addFilter(sensitive_filter)

    file_handler = RotatingFileHandler(
        settings.app_log_dir / "distribuidora.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(sensitive_filter)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(getattr(logging, settings.app_log_level))
    root.addHandler(console)
    root.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """Cria um logger nomeado sem configuração implícita."""
    return logging.getLogger(name)

