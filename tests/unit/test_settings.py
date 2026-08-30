"""Testes das configurações da aplicação."""

from __future__ import annotations

from pathlib import Path

import pytest

from config.settings import SettingsError, load_settings


MONGO_ENV_NAMES = (
    "MONGODB_URI",
    "MONGODB_DATABASE",
    "MONGODB_MIN_POOL_SIZE",
    "MONGODB_MAX_POOL_SIZE",
)


@pytest.fixture(autouse=True)
def clear_mongo_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in MONGO_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_load_settings_from_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "MONGODB_URI=mongodb://db-server:27017\n"
        "MONGODB_DATABASE=adega_teste\n",
        encoding="utf-8",
    )

    settings = load_settings(env_file)

    assert settings.mongodb_uri == "mongodb://db-server:27017"
    assert settings.mongodb_database == "adega_teste"
    assert settings.mongo_client_options()["tz_aware"] is True


def test_environment_overrides_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("MONGODB_URI=mongodb://old:27017\n", encoding="utf-8")
    monkeypatch.setenv("MONGODB_URI", "mongodb://new:27017")

    assert load_settings(env_file).mongodb_uri == "mongodb://new:27017"


def test_missing_uri_is_reported(tmp_path: Path) -> None:
    with pytest.raises(SettingsError, match="mongodb_uri"):
        load_settings(tmp_path / "missing.env")


def test_invalid_pool_sizes_are_reported(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "MONGODB_URI=mongodb://localhost:27017\n"
        "MONGODB_MIN_POOL_SIZE=10\n"
        "MONGODB_MAX_POOL_SIZE=2\n",
        encoding="utf-8",
    )
    settings = load_settings(env_file)

    with pytest.raises(SettingsError, match="MIN_POOL_SIZE"):
        settings.mongo_client_options()

