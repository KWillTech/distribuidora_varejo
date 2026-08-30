"""Carregamento e validação das configurações por variáveis de ambiente."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class SettingsError(RuntimeError):
    """Indica configuração ausente ou inválida."""


class Settings(BaseModel):
    """Configurações validadas da aplicação."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    app_name: str = "Adega do Bruninho"
    app_env: Literal["development", "testing", "production"] = "development"
    app_debug: bool = False
    app_log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    app_log_dir: Path = Path("logs")

    mongodb_uri: str = Field(min_length=10)
    mongodb_database: str = Field(default="distribuidora_varejo", min_length=1)
    mongodb_connect_timeout_ms: int = Field(default=5_000, ge=500, le=120_000)
    mongodb_server_selection_timeout_ms: int = Field(
        default=5_000, ge=500, le=120_000
    )
    mongodb_max_pool_size: int = Field(default=50, ge=1, le=1_000)
    mongodb_min_pool_size: int = Field(default=1, ge=0, le=1_000)
    mongodb_tls: bool = False
    initial_admin_password: str | None = None

    @field_validator("mongodb_uri")
    @classmethod
    def validate_mongodb_uri(cls, value: str) -> str:
        """Aceita somente URIs reconhecidas pelo driver MongoDB."""
        if not value.startswith(("mongodb://", "mongodb+srv://")):
            raise ValueError("deve começar com mongodb:// ou mongodb+srv://")
        return value

    @field_validator("mongodb_database")
    @classmethod
    def validate_database_name(cls, value: str) -> str:
        """Rejeita caracteres proibidos em nomes de banco MongoDB."""
        forbidden = set('/\\. "*$<>:|?')
        if any(character in forbidden for character in value):
            raise ValueError("contém caracteres não permitidos")
        return value

    @field_validator("app_log_dir")
    @classmethod
    def resolve_log_dir(cls, value: Path) -> Path:
        """Transforma diretórios relativos em caminhos dentro do projeto."""
        return value if value.is_absolute() else PROJECT_ROOT / value

    def mongo_client_options(self) -> dict[str, object]:
        """Retorna opções seguras para criação do MongoClient."""
        if self.mongodb_min_pool_size > self.mongodb_max_pool_size:
            raise SettingsError(
                "MONGODB_MIN_POOL_SIZE não pode exceder MONGODB_MAX_POOL_SIZE"
            )
        return {
            "connectTimeoutMS": self.mongodb_connect_timeout_ms,
            "serverSelectionTimeoutMS": self.mongodb_server_selection_timeout_ms,
            "maxPoolSize": self.mongodb_max_pool_size,
            "minPoolSize": self.mongodb_min_pool_size,
            "tls": self.mongodb_tls,
            "tz_aware": True,
            "retryWrites": True,
            "appname": self.app_name,
        }


ENV_FIELD_MAP = {
    "APP_NAME": "app_name",
    "APP_ENV": "app_env",
    "APP_DEBUG": "app_debug",
    "APP_LOG_LEVEL": "app_log_level",
    "APP_LOG_DIR": "app_log_dir",
    "MONGODB_URI": "mongodb_uri",
    "MONGODB_DATABASE": "mongodb_database",
    "MONGODB_CONNECT_TIMEOUT_MS": "mongodb_connect_timeout_ms",
    "MONGODB_SERVER_SELECTION_TIMEOUT_MS": "mongodb_server_selection_timeout_ms",
    "MONGODB_MAX_POOL_SIZE": "mongodb_max_pool_size",
    "MONGODB_MIN_POOL_SIZE": "mongodb_min_pool_size",
    "MONGODB_TLS": "mongodb_tls",
    "INITIAL_ADMIN_PASSWORD": "initial_admin_password",
}


def load_settings(env_file: Path | None = None) -> Settings:
    """Carrega `.env`, permitindo que o ambiente do processo tenha precedência."""
    import os

    path = env_file if env_file is not None else PROJECT_ROOT / ".env"
    file_values = dotenv_values(path) if path.exists() else {}
    raw: dict[str, object] = {}
    for env_name, field_name in ENV_FIELD_MAP.items():
        value = os.getenv(env_name, file_values.get(env_name))
        if value is not None and value != "":
            raw[field_name] = value
    try:
        return Settings.model_validate(raw)
    except ValidationError as exc:
        messages = "; ".join(
            f"{'.'.join(map(str, error['loc']))}: {error['msg']}"
            for error in exc.errors()
        )
        raise SettingsError(messages) from exc


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retorna uma única instância de configuração durante o processo."""
    return load_settings()
