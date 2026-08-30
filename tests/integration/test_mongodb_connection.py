"""Teste opcional contra um MongoDB real configurado no ambiente."""

from __future__ import annotations

import os

import pytest

from config.database import MongoDatabase
from config.settings import Settings


@pytest.mark.integration
def test_real_mongodb_connection() -> None:
    uri = os.getenv("TEST_MONGODB_URI")
    if not uri:
        pytest.skip("Defina TEST_MONGODB_URI para executar a integração")
    settings = Settings(
        mongodb_uri=uri,
        mongodb_database=os.getenv("TEST_MONGODB_DATABASE", "distribuidora_test"),
    )

    with MongoDatabase(settings) as manager:
        assert manager.health_check() is True

