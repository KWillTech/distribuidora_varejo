"""Testes unitários da infraestrutura MongoDB."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pymongo.errors import ServerSelectionTimeoutError

from config.database import DatabaseConnectionError, MongoDatabase
from config.settings import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(mongodb_uri="mongodb://localhost:27017")


def test_connect_pings_server_and_reuses_database(settings: Settings) -> None:
    client = MagicMock()
    client.admin.command.return_value = {"ok": 1.0}
    factory = MagicMock(return_value=client)
    manager = MongoDatabase(settings, client_factory=factory)

    first = manager.connect()
    second = manager.connect()

    assert first is second
    factory.assert_called_once()
    client.admin.command.assert_called_once_with("ping")


def test_connection_error_does_not_expose_uri(settings: Settings) -> None:
    client = MagicMock()
    client.admin.command.side_effect = ServerSelectionTimeoutError("secret-host")
    manager = MongoDatabase(settings, client_factory=MagicMock(return_value=client))

    with pytest.raises(DatabaseConnectionError) as caught:
        manager.connect()

    assert "secret-host" not in str(caught.value)
    client.close.assert_called_once()


def test_close_releases_client(settings: Settings) -> None:
    client = MagicMock()
    client.admin.command.return_value = {"ok": 1.0}
    manager = MongoDatabase(settings, client_factory=MagicMock(return_value=client))
    manager.connect()

    manager.close()

    client.close.assert_called_once()


def test_base_indexes_are_created(settings: Settings) -> None:
    client = MagicMock()
    client.admin.command.return_value = {"ok": 1.0}
    collections = {
        "usuarios": MagicMock(),
        "perfis": MagicMock(),
        "auditoria": MagicMock(),
        "configuracoes": MagicMock(),
        "vendas": MagicMock(),
        "comandas": MagicMock(),
        "pedidos": MagicMock(),
        "entregas": MagicMock(),
        "produtos": MagicMock(),
        "clientes": MagicMock(),
        "fornecedores": MagicMock(),
        "compras": MagicMock(),
        "categorias": MagicMock(),
        "movimentacoes_estoque": MagicMock(),
        "lotes": MagicMock(),
        "contas_pagar": MagicMock(),
        "contas_receber": MagicMock(),
        "movimentacoes_fiado": MagicMock(),
        "pagamentos_fiado": MagicMock(),
        "despesas": MagicMock(),
        "receitas": MagicMock(),
        "pagamentos_financeiros": MagicMock(),
        "caixas": MagicMock(),
        "movimentacoes_caixa": MagicMock(),
    }
    database = client[settings.mongodb_database]
    database.__getitem__.side_effect = collections.__getitem__
    manager = MongoDatabase(settings, client_factory=MagicMock(return_value=client))

    manager.ensure_base_indexes()

    assert collections["usuarios"].create_index.call_count == 3
    assert collections["perfis"].create_index.call_count == 2
    assert collections["auditoria"].create_index.call_count == 2
    assert collections["configuracoes"].create_index.call_count == 1
    assert collections["vendas"].create_index.call_count == 4
    assert collections["comandas"].create_index.call_count == 6
    assert collections["pedidos"].create_index.call_count == 2
    assert collections["entregas"].create_index.call_count == 3
    assert collections["produtos"].create_index.call_count == 8
    assert collections["clientes"].create_index.call_count == 5
    assert collections["fornecedores"].create_index.call_count == 4
    assert collections["compras"].create_index.call_count == 4
    assert collections["categorias"].create_index.call_count == 2
    assert collections["movimentacoes_estoque"].create_index.call_count == 3
    assert collections["lotes"].create_index.call_count == 3
    assert collections["contas_pagar"].create_index.call_count == 3
    assert collections["contas_receber"].create_index.call_count == 3
    assert collections["movimentacoes_fiado"].create_index.call_count == 2
    assert collections["pagamentos_fiado"].create_index.call_count == 2
    assert collections["despesas"].create_index.call_count == 2
    assert collections["receitas"].create_index.call_count == 1
    assert collections["pagamentos_financeiros"].create_index.call_count == 1
    assert collections["caixas"].create_index.call_count == 2
    assert collections["movimentacoes_caixa"].create_index.call_count == 2
