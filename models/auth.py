"""Modelos de autenticação, usuários e controle de acesso."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


def utc_now() -> datetime:
    """Retorna o instante atual em UTC."""
    return datetime.now(timezone.utc)


class ProfileCode(StrEnum):
    ADMIN = "administrador"
    MANAGER = "gerente"
    CASHIER = "caixa"
    STOCK = "estoquista"
    FINANCE = "financeiro"
    DELIVERY = "entregador"


class Permission(StrEnum):
    USERS_VIEW = "usuarios.visualizar"
    USERS_CREATE = "usuarios.cadastrar"
    USERS_EDIT = "usuarios.editar"
    USERS_DEACTIVATE = "usuarios.inativar"
    USERS_RESET_PASSWORD = "usuarios.redefinir_senha"
    PERMISSIONS_MANAGE = "permissoes.gerenciar"
    DASHBOARD_VIEW = "dashboard.visualizar"
    CUSTOMERS_VIEW = "clientes.visualizar"
    CUSTOMERS_CREATE = "clientes.cadastrar"
    CUSTOMERS_EDIT = "clientes.editar"
    CUSTOMERS_DEACTIVATE = "clientes.inativar"
    SUPPLIERS_VIEW = "fornecedores.visualizar"
    SUPPLIERS_CREATE = "fornecedores.cadastrar"
    SUPPLIERS_EDIT = "fornecedores.editar"
    SUPPLIERS_DEACTIVATE = "fornecedores.inativar"
    PRODUCTS_VIEW = "produtos.visualizar"
    PRODUCTS_CREATE = "produtos.cadastrar"
    PRODUCTS_EDIT = "produtos.editar"
    PRODUCTS_DEACTIVATE = "produtos.inativar"
    CATEGORIES_MANAGE = "categorias.gerenciar"
    PRODUCTS_CHANGE_PRICE = "produtos.alterar_precos"
    COST_VIEW = "custos.visualizar"
    PROFIT_VIEW = "lucro.visualizar"
    STOCK_VIEW = "estoque.visualizar"
    STOCK_ADJUST = "estoque.ajustar"
    PURCHASES_CREATE = "compras.cadastrar"
    PURCHASES_CANCEL = "compras.cancelar"
    POS_ACCESS = "pdv.acessar"
    SALES_VIEW_OWN = "vendas.visualizar_proprias"
    SALES_VIEW_ALL = "vendas.visualizar_todas"
    SALES_CANCEL = "vendas.cancelar"
    DISCOUNT_APPROVE = "descontos.aprovar"
    CASH_OPEN = "caixa.abrir"
    CASH_WITHDRAW = "caixa.sangria"
    CASH_CLOSE = "caixa.fechar"
    FINANCE_VIEW = "financeiro.visualizar"
    FINANCE_MANAGE = "financeiro.movimentar"
    REPORTS_VIEW = "relatorios.visualizar"
    REPORTS_EXPORT = "relatorios.exportar"
    DELIVERIES_OWN = "entregas.visualizar_proprias"
    DELIVERIES_MANAGE = "entregas.gerenciar"
    ORDERS_CREATE = "pedidos.cadastrar"
    AUDIT_VIEW = "auditoria.visualizar"
    SETTINGS_MANAGE = "configuracoes.gerenciar"
    BACKUP_CREATE = "backup.criar"
    BACKUP_RESTORE = "backup.restaurar"
    CREDIT_VIEW = "fiado.visualizar"
    CREDIT_SALE = "fiado.realizar_venda"
    CREDIT_RECEIVE = "fiado.receber_pagamento"
    CREDIT_ENABLE = "fiado.habilitar_cliente"
    CREDIT_LIMIT = "fiado.alterar_limite"
    CREDIT_BLOCK = "fiado.bloquear_cliente"
    CREDIT_UNBLOCK = "fiado.desbloquear_cliente"
    CREDIT_RELEASE_OVERDUE = "fiado.liberar_cliente_inadimplente"
    CREDIT_EXCEED_LIMIT = "fiado.ultrapassar_limite"
    CREDIT_DISCOUNT = "fiado.aplicar_desconto"
    CREDIT_INTEREST = "fiado.aplicar_juros"
    CREDIT_RENEGOTIATE = "fiado.renegociar"
    CREDIT_CANCEL = "fiado.cancelar"
    CREDIT_REVERSE_PAYMENT = "fiado.estornar_pagamento"
    CREDIT_EXPORT = "fiado.exportar_relatorio"
    TABS_VIEW = "comandas.visualizar"
    TABS_OPEN = "comandas.abrir"
    TABS_LINK_CUSTOMER = "comandas.vincular_cliente"
    TABS_ADD_ITEM = "comandas.adicionar_item"
    TABS_EDIT_ITEM = "comandas.alterar_item"
    TABS_REMOVE_ITEM = "comandas.remover_item"
    TABS_DISCOUNT = "comandas.aplicar_desconto"
    TABS_TRANSFER_ITEM = "comandas.transferir_item"
    TABS_MERGE = "comandas.unir"
    TABS_REQUEST_CLOSE = "comandas.solicitar_fechamento"
    TABS_FINALIZE = "comandas.finalizar"
    TABS_CANCEL = "comandas.cancelar"
    TABS_PRINT = "comandas.imprimir"
    TABS_HISTORY = "comandas.consultar_historico"


class Profile(BaseModel):
    """Perfil RBAC persistido no MongoDB."""

    model_config = ConfigDict(str_strip_whitespace=True)
    id: str | None = None
    code: ProfileCode
    name: str = Field(min_length=2, max_length=80)
    permissions: set[Permission] = Field(default_factory=set)
    system: bool = True
    active: bool = True


class User(BaseModel):
    """Usuário sem expor o hash de senha às views."""

    model_config = ConfigDict(str_strip_whitespace=True)
    id: str | None = None
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9._-]+$")
    email: str = Field(min_length=5, max_length=254)
    full_name: str = Field(min_length=3, max_length=120)
    profile_code: ProfileCode
    individual_grants: set[Permission] = Field(default_factory=set)
    individual_denials: set[Permission] = Field(default_factory=set)
    active: bool = True
    must_change_password: bool = True
    failed_attempts: int = Field(default=0, ge=0)
    locked_until: datetime | None = None
    last_access_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.lower()

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("e-mail inválido")
        return value


class UserCreate(BaseModel):
    """Entrada validada para criação de usuário."""

    model_config = ConfigDict(str_strip_whitespace=True)
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9._-]+$")
    email: str = Field(min_length=5, max_length=254)
    full_name: str = Field(min_length=3, max_length=120)
    profile_code: ProfileCode
    temporary_password: str = Field(min_length=10, max_length=128)
    individual_grants: set[Permission] = Field(default_factory=set)
    individual_denials: set[Permission] = Field(default_factory=set)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("e-mail inválido")
        return value


class AuthenticatedSession(BaseModel):
    """Sessão mantida apenas em memória durante a execução."""

    session_id: str
    user: User
    permissions: set[Permission]
    authenticated_at: datetime = Field(default_factory=utc_now)
