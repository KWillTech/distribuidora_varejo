"""Perfis padrão e verificação central de permissões."""

from __future__ import annotations

from models.auth import AuthenticatedSession, Permission, Profile, ProfileCode, User


class AuthorizationError(PermissionError):
    """Operação negada pelo controle de acesso."""


PROFILE_NAMES = {
    ProfileCode.ADMIN: "Administrador",
    ProfileCode.MANAGER: "Gerente",
    ProfileCode.CASHIER: "Caixa ou atendente",
    ProfileCode.STOCK: "Estoquista",
    ProfileCode.FINANCE: "Financeiro",
    ProfileCode.DELIVERY: "Entregador",
}


def default_profiles() -> list[Profile]:
    """Monta os seis perfis do escopo, com privilégios mínimos explícitos."""
    all_permissions = set(Permission)
    grants = {
        ProfileCode.ADMIN: all_permissions,
        ProfileCode.MANAGER: {
            Permission.DASHBOARD_VIEW, Permission.CUSTOMERS_VIEW, Permission.CUSTOMERS_CREATE, Permission.CUSTOMERS_EDIT, Permission.CUSTOMERS_DEACTIVATE,
            Permission.SUPPLIERS_VIEW, Permission.SUPPLIERS_CREATE, Permission.SUPPLIERS_EDIT, Permission.SUPPLIERS_DEACTIVATE, Permission.PRODUCTS_VIEW,
            Permission.PRODUCTS_CREATE, Permission.PRODUCTS_EDIT, Permission.PRODUCTS_DEACTIVATE, Permission.CATEGORIES_MANAGE, Permission.PRODUCTS_CHANGE_PRICE, Permission.COST_VIEW,
            Permission.PROFIT_VIEW, Permission.STOCK_VIEW, Permission.STOCK_ADJUST,
            Permission.PURCHASES_CREATE, Permission.PURCHASES_CANCEL, Permission.POS_ACCESS, Permission.SALES_VIEW_ALL, Permission.SALES_CANCEL,
            Permission.DISCOUNT_APPROVE, Permission.CASH_OPEN, Permission.CASH_WITHDRAW, Permission.CASH_CLOSE, Permission.FINANCE_VIEW, Permission.REPORTS_VIEW,
            Permission.DELIVERIES_MANAGE,
            Permission.CREDIT_VIEW, Permission.CREDIT_SALE, Permission.CREDIT_RECEIVE,
            Permission.CREDIT_ENABLE, Permission.CREDIT_LIMIT, Permission.CREDIT_BLOCK,
            Permission.CREDIT_UNBLOCK, Permission.CREDIT_RELEASE_OVERDUE,
            Permission.CREDIT_EXCEED_LIMIT, Permission.CREDIT_DISCOUNT,
            Permission.CREDIT_INTEREST, Permission.CREDIT_RENEGOTIATE,
            Permission.CREDIT_CANCEL, Permission.CREDIT_REVERSE_PAYMENT,
            Permission.CREDIT_EXPORT,
            Permission.TABS_VIEW, Permission.TABS_OPEN, Permission.TABS_LINK_CUSTOMER,
            Permission.TABS_ADD_ITEM, Permission.TABS_EDIT_ITEM, Permission.TABS_REMOVE_ITEM,
            Permission.TABS_DISCOUNT, Permission.TABS_TRANSFER_ITEM, Permission.TABS_MERGE,
            Permission.TABS_REQUEST_CLOSE, Permission.TABS_FINALIZE, Permission.TABS_CANCEL,
            Permission.TABS_PRINT, Permission.TABS_HISTORY,
        },
        ProfileCode.CASHIER: {
            Permission.POS_ACCESS, Permission.PRODUCTS_VIEW, Permission.CUSTOMERS_VIEW,
            Permission.CUSTOMERS_CREATE, Permission.SALES_VIEW_OWN, Permission.CASH_OPEN,
            Permission.CASH_WITHDRAW, Permission.CASH_CLOSE, Permission.ORDERS_CREATE,
            Permission.CREDIT_VIEW, Permission.CREDIT_SALE, Permission.CREDIT_RECEIVE,
            Permission.TABS_VIEW, Permission.TABS_OPEN, Permission.TABS_LINK_CUSTOMER,
            Permission.TABS_ADD_ITEM, Permission.TABS_EDIT_ITEM, Permission.TABS_REQUEST_CLOSE,
            Permission.TABS_FINALIZE, Permission.TABS_PRINT, Permission.TABS_HISTORY,
        },
        ProfileCode.STOCK: {
            Permission.PRODUCTS_VIEW, Permission.PRODUCTS_CREATE, Permission.PRODUCTS_EDIT, Permission.PRODUCTS_DEACTIVATE, Permission.CATEGORIES_MANAGE, Permission.SUPPLIERS_VIEW,
            Permission.PURCHASES_CREATE, Permission.PURCHASES_CANCEL, Permission.STOCK_VIEW, Permission.STOCK_ADJUST,
            Permission.REPORTS_VIEW, Permission.DELIVERIES_MANAGE,
            Permission.TABS_VIEW,
        },
        ProfileCode.FINANCE: {
            Permission.SALES_VIEW_ALL, Permission.FINANCE_VIEW, Permission.REPORTS_VIEW,
            Permission.REPORTS_EXPORT, Permission.FINANCE_MANAGE, Permission.CREDIT_VIEW,
            Permission.CREDIT_RECEIVE, Permission.CREDIT_DISCOUNT, Permission.CREDIT_INTEREST,
            Permission.CREDIT_RENEGOTIATE, Permission.CREDIT_EXPORT,
            Permission.TABS_VIEW, Permission.TABS_HISTORY,
        },
        ProfileCode.DELIVERY: {Permission.DELIVERIES_OWN},
    }
    return [Profile(code=code, name=PROFILE_NAMES[code], permissions=grants[code]) for code in ProfileCode]


def effective_permissions(user: User, profile: Profile) -> set[Permission]:
    """Aplica bloqueios individuais após permissões do perfil e liberações."""
    return (profile.permissions | user.individual_grants) - user.individual_denials


def require_permission(session: AuthenticatedSession, permission: Permission) -> None:
    """Impede a operação mesmo quando chamada fora da interface."""
    if permission not in session.permissions:
        raise AuthorizationError(f"Permissão necessária: {permission.value}")
