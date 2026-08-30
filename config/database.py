"""Gerenciamento centralizado da conexão com o MongoDB."""

from __future__ import annotations

from collections.abc import Callable
from threading import RLock
from typing import Any

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.database import Database
from pymongo.errors import PyMongoError

from config.settings import Settings
from utils.logging_config import get_logger


logger = get_logger(__name__)
ClientFactory = Callable[..., MongoClient]


class DatabaseConnectionError(RuntimeError):
    """Erro seguro apresentado quando a conexão não pode ser estabelecida."""


class MongoDatabase:
    """Mantém um pool de conexões e expõe o banco para os repositórios."""

    def __init__(
        self,
        settings: Settings,
        client_factory: ClientFactory = MongoClient,
    ) -> None:
        self._settings = settings
        self._client_factory = client_factory
        self._client: MongoClient | None = None
        self._database: Database | None = None
        self._lock = RLock()

    @property
    def database(self) -> Database:
        """Retorna o banco conectado, conectando sob demanda."""
        if self._database is None:
            self.connect()
        if self._database is None:  # pragma: no cover - garantia para o type checker
            raise DatabaseConnectionError("Banco de dados indisponível")
        return self._database

    def connect(self) -> Database:
        """Cria o cliente, valida o servidor com ping e reutiliza o pool."""
        with self._lock:
            if self._database is not None:
                return self._database
            client: MongoClient | None = None
            try:
                client = self._client_factory(
                    self._settings.mongodb_uri,
                    **self._settings.mongo_client_options(),
                )
                client.admin.command("ping")
                database = client[self._settings.mongodb_database]
                self._client = client
                self._database = database
                logger.info("Conexão com MongoDB validada")
                return database
            except (PyMongoError, OSError, ValueError) as exc:
                if client is not None:
                    client.close()
                logger.error("Falha ao conectar ao MongoDB: %s", type(exc).__name__)
                raise DatabaseConnectionError(
                    "Não foi possível conectar ao MongoDB. Verifique o servidor e a configuração."
                ) from exc

    def health_check(self) -> bool:
        """Confirma que o servidor conectado continua respondendo."""
        try:
            self.connect()
            if self._client is None:
                return False
            return self._client.admin.command("ping").get("ok") == 1.0
        except DatabaseConnectionError:
            return False

    def ensure_base_indexes(self) -> None:
        """Cria índices de infraestrutura que já são definidos nesta etapa."""
        indexes: dict[str, list[tuple[list[tuple[str, int]], dict[str, Any]]]] = {
            "usuarios": [
                ([("usuario", ASCENDING)], {"unique": True, "name": "uq_usuario"}),
                ([("email_normalizado", ASCENDING)], {"unique": True, "name": "uq_email"}),
                ([("status", ASCENDING)], {"name": "ix_usuario_status"}),
            ],
            "perfis": [
                ([("codigo", ASCENDING)], {"unique": True, "name": "uq_perfil_codigo"}),
                ([("ativo", ASCENDING)], {"name": "ix_perfil_ativo"}),
            ],
            "auditoria": [
                ([("data_hora", DESCENDING)], {"name": "ix_auditoria_data"}),
                ([("usuario_id", ASCENDING), ("data_hora", DESCENDING)], {"name": "ix_auditoria_usuario_data"}),
            ],
            "configuracoes": [
                ([("chave", ASCENDING)], {"unique": True, "name": "uq_configuracao_chave"}),
            ],
            "vendas": [
                ([("data_hora", DESCENDING)], {"name": "ix_venda_data"}),
                ([("status", ASCENDING), ("data_hora", DESCENDING)], {"name": "ix_venda_status_data"}),
                ([("usuario_id", ASCENDING), ("data_hora", DESCENDING)], {"name": "ix_venda_usuario_data"}),
                ([("comanda_id", ASCENDING)], {"unique": True, "name": "uq_venda_comanda", "partialFilterExpression": {"comanda_id": {"$type": "string"}}}),
            ],
            "comandas": [
                ([("numero", ASCENDING)], {"unique": True, "name": "uq_comanda_numero"}),
                ([("posicao", ASCENDING), ("status", ASCENDING)], {"name": "ix_comanda_posicao_status"}),
                ([("status", ASCENDING), ("data_abertura", DESCENDING)], {"name": "ix_comanda_status_abertura"}),
                ([("cliente_id", ASCENDING), ("status", ASCENDING)], {"name": "ix_comanda_cliente_status"}),
                ([("usuario_responsavel_id", ASCENDING), ("status", ASCENDING)], {"name": "ix_comanda_usuario_status"}),
                ([("venda_id", ASCENDING)], {"unique": True, "name": "uq_comanda_venda", "partialFilterExpression": {"venda_id": {"$type": "string"}}}),
            ],
            "pedidos": [
                ([("status", ASCENDING), ("data_hora", DESCENDING)], {"name": "ix_pedido_status_data"}),
                ([("numero", ASCENDING)], {"unique": True, "name": "uq_pedido_numero"}),
            ],
            "entregas": [
                ([("status", ASCENDING), ("criado_em", DESCENDING)], {"name": "ix_entrega_status_data"}),
                ([("pedido_id", ASCENDING)], {"unique": True, "name": "uq_entrega_pedido"}),
                ([("entregador_id", ASCENDING), ("status", ASCENDING)], {"name": "ix_entrega_entregador_status"}),
            ],
            "produtos": [
                ([("ativo", ASCENDING)], {"name": "ix_produto_ativo"}),
                ([("data_validade", ASCENDING)], {"name": "ix_produto_validade"}),
                ([("codigo_interno", ASCENDING)], {"unique": True, "name": "uq_produto_codigo"}),
                ([("codigo_barras_unidade", ASCENDING)], {"unique": True, "name": "uq_produto_barra_unidade", "partialFilterExpression": {"codigo_barras_unidade": {"$type": "string"}}}),
                ([("codigo_barras_fardo", ASCENDING)], {"unique": True, "name": "uq_produto_barra_fardo", "partialFilterExpression": {"codigo_barras_fardo": {"$type": "string"}}}),
                ([("codigos_barras", ASCENDING)], {"unique": True, "name": "uq_produto_todos_codigos_barras", "partialFilterExpression": {"codigos_barras.0": {"$exists": True}}}),
                ([("categoria_id", ASCENDING), ("nome", ASCENDING)], {"name": "ix_produto_categoria_nome"}),
                ([("nome", ASCENDING)], {"name": "ix_produto_nome"}),
            ],
            "categorias": [
                ([("nome_normalizado", ASCENDING)], {"unique": True, "name": "uq_categoria_nome"}),
                ([("ativo", ASCENDING), ("nome", ASCENDING)], {"name": "ix_categoria_status_nome"}),
            ],
            "clientes": [
                ([("cpf", ASCENDING)], {"unique": True, "name": "uq_cliente_cpf", "partialFilterExpression": {"cpf": {"$type": "string"}}}),
                ([("nome_completo", ASCENDING)], {"name": "ix_cliente_nome"}),
                ([("telefone", ASCENDING)], {"name": "ix_cliente_telefone"}),
                ([("ativo", ASCENDING), ("nome_completo", ASCENDING)], {"name": "ix_cliente_status_nome"}),
                ([("fiado_habilitado", ASCENDING), ("fiado_status", ASCENDING)], {"name": "ix_cliente_fiado_status"}),
            ],
            "fornecedores": [
                ([("documento", ASCENDING)], {"unique": True, "name": "uq_fornecedor_documento"}),
                ([("razao_social", ASCENDING)], {"name": "ix_fornecedor_razao_social"}),
                ([("nome_fantasia", ASCENDING)], {"name": "ix_fornecedor_nome_fantasia"}),
                ([("ativo", ASCENDING), ("razao_social", ASCENDING)], {"name": "ix_fornecedor_status_razao"}),
            ],
            "compras": [
                ([("fornecedor_id", ASCENDING), ("data_hora", DESCENDING)], {"name": "ix_compra_fornecedor_data"}),
                ([("status", ASCENDING), ("data_hora", DESCENDING)], {"name": "ix_compra_status_data"}),
                ([("numero", ASCENDING)], {"unique": True, "name": "uq_compra_numero"}),
                ([("numero_nota", ASCENDING)], {"name": "ix_compra_nfe"}),
            ],
            "contas_pagar": [
                ([("status", ASCENDING), ("vencimento", ASCENDING)], {"name": "ix_conta_pagar_status_vencimento"}),
                ([("compra_id", ASCENDING)], {"name": "ix_conta_pagar_compra"}),
                ([("fornecedor_id", ASCENDING), ("vencimento", ASCENDING)], {"name": "ix_conta_pagar_fornecedor_vencimento"}),
            ],
            "contas_receber": [
                ([("status", ASCENDING), ("vencimento", ASCENDING)], {"name": "ix_conta_receber_status_vencimento"}),
                ([("venda_id", ASCENDING)], {"unique": True, "name": "uq_conta_receber_venda", "partialFilterExpression": {"origem": "fiado"}}),
                ([("cliente_id", ASCENDING), ("status", ASCENDING), ("vencimento", ASCENDING)], {"name": "ix_fiado_cliente_status_vencimento"}),
            ],
            "movimentacoes_fiado": [
                ([("cliente_id", ASCENDING), ("data_hora", ASCENDING)], {"name": "ix_mov_fiado_cliente_data"}),
                ([("conta_receber_id", ASCENDING), ("data_hora", ASCENDING)], {"name": "ix_mov_fiado_conta_data"}),
            ],
            "pagamentos_fiado": [
                ([("cliente_id", ASCENDING), ("data_hora", DESCENDING)], {"name": "ix_pag_fiado_cliente_data"}),
                ([("data_hora", DESCENDING)], {"name": "ix_pag_fiado_data"}),
            ],
            "despesas": [
                ([("status", ASCENDING), ("vencimento", ASCENDING)], {"name": "ix_despesa_status_vencimento"}),
                ([("data_hora", DESCENDING)], {"name": "ix_despesa_data"}),
            ],
            "receitas": [
                ([("status", ASCENDING), ("vencimento", ASCENDING)], {"name": "ix_receita_status_vencimento"}),
            ],
            "pagamentos_financeiros": [
                ([("lancamento_id", ASCENDING), ("data_hora", DESCENDING)], {"name": "ix_pagamento_lancamento_data"}),
            ],
            "caixas": [
                ([("usuario_id", ASCENDING), ("status", ASCENDING)], {"name": "ix_caixa_usuario_status"}),
                ([("aberto_em", DESCENDING)], {"name": "ix_caixa_abertura"}),
            ],
            "movimentacoes_caixa": [
                ([("caixa_id", ASCENDING), ("data_hora", DESCENDING)], {"name": "ix_movimento_caixa_data"}),
                ([("tipo", ASCENDING), ("data_hora", DESCENDING)], {"name": "ix_movimento_caixa_tipo"}),
            ],
            "movimentacoes_estoque": [
                ([("produto_id", ASCENDING), ("data_hora", DESCENDING)], {"name": "ix_movimento_produto_data"}),
                ([("tipo_movimentacao", ASCENDING), ("data_hora", DESCENDING)], {"name": "ix_movimento_tipo_data"}),
                ([("usuario_id", ASCENDING), ("data_hora", DESCENDING)], {"name": "ix_movimento_usuario_data"}),
            ],
            "lotes": [
                ([("produto_id", ASCENDING), ("codigo", ASCENDING)], {"unique": True, "name": "uq_lote_produto_codigo"}),
                ([("data_validade", ASCENDING)], {"name": "ix_lote_validade"}),
                ([("produto_id", ASCENDING), ("quantidade_unidades", ASCENDING)], {"name": "ix_lote_produto_saldo"}),
            ],
        }
        for collection_name, definitions in indexes.items():
            collection = self.database[collection_name]
            for keys, options in definitions:
                collection.create_index(keys, **options)

    def close(self) -> None:
        """Fecha o cliente e permite uma conexão futura limpa."""
        with self._lock:
            if self._client is not None:
                self._client.close()
            self._client = None
            self._database = None
            logger.info("Conexão com MongoDB encerrada")

    def __enter__(self) -> "MongoDatabase":
        self.connect()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
