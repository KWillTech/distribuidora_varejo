"""Regras e autorização do módulo de fornecedores."""

from typing import Any

from models.auth import AuthenticatedSession, Permission
from models.supplier import Supplier, SupplierInput, SupplierPage
from repositories.auth import AuditRepository
from repositories.suppliers import SupplierRepository
from services.rbac import require_permission


class SupplierService:
    def __init__(self, repository: SupplierRepository, audit: AuditRepository) -> None:
        self._repository = repository; self._audit = audit

    def list_page(self, session: AuthenticatedSession, **filters) -> SupplierPage:
        require_permission(session, Permission.SUPPLIERS_VIEW)
        page = filters.get("page", 1); size = filters.get("page_size", 20)
        if page < 1 or size not in (10, 20, 50, 100): raise ValueError("Paginação inválida.")
        return self._repository.list_page(**filters)

    def get(self, session: AuthenticatedSession, supplier_id: str) -> Supplier:
        require_permission(session, Permission.SUPPLIERS_VIEW)
        supplier = self._repository.get(supplier_id)
        if supplier is None: raise ValueError("Fornecedor não encontrado.")
        return supplier

    def create(self, session: AuthenticatedSession, data: SupplierInput) -> Supplier:
        require_permission(session, Permission.SUPPLIERS_CREATE)
        result = self._repository.create(data); self._audit.record(user=session.user, action="fornecedor_criado", module="fornecedores", affected_id=result.id); return result

    def update(self, session: AuthenticatedSession, supplier_id: str, data: SupplierInput) -> Supplier:
        require_permission(session, Permission.SUPPLIERS_EDIT)
        result = self._repository.update(supplier_id, data)
        if result is None: raise ValueError("Fornecedor não encontrado.")
        self._audit.record(user=session.user, action="fornecedor_alterado", module="fornecedores", affected_id=supplier_id); return result

    def set_active(self, session: AuthenticatedSession, supplier_id: str, active: bool, reason: str) -> None:
        require_permission(session, Permission.SUPPLIERS_DEACTIVATE)
        if not reason.strip(): raise ValueError("Informe o motivo da alteração.")
        if not self._repository.set_active(supplier_id, active): raise ValueError("Fornecedor não encontrado.")
        self._audit.record(user=session.user, action="fornecedor_ativado" if active else "fornecedor_inativado", module="fornecedores", affected_id=supplier_id, reason=reason)

    def purchase_details(self, session: AuthenticatedSession, supplier_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        require_permission(session, Permission.SUPPLIERS_VIEW)
        return self._repository.purchase_history(supplier_id), self._repository.latest_costs(supplier_id)

    def active_options(self, session: AuthenticatedSession) -> list[tuple[str, str, str | None]]:
        require_permission(session, Permission.SUPPLIERS_VIEW); return self._repository.active_options()
