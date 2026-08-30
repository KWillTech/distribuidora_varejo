"""Regras de negócio e autorização do módulo de clientes."""

from __future__ import annotations

from datetime import date
from typing import Any

from models.auth import AuthenticatedSession, Permission
from models.customer import Customer, CustomerInput, CustomerPage
from repositories.auth import AuditRepository
from repositories.customers import CustomerRepository
from services.rbac import require_permission


class CustomerService:
    def __init__(self, repository: CustomerRepository, audit: AuditRepository) -> None:
        self._repository = repository
        self._audit = audit

    def list_page(self, session: AuthenticatedSession, *, search: str = "", active: bool | None = True, page: int = 1, page_size: int = 20) -> CustomerPage:
        require_permission(session, Permission.CUSTOMERS_VIEW)
        if page < 1 or page_size not in (10, 20, 50, 100):
            raise ValueError("Paginação inválida.")
        return self._repository.list_page(search=search, active=active, page=page, page_size=page_size)

    def get(self, session: AuthenticatedSession, customer_id: str) -> Customer:
        require_permission(session, Permission.CUSTOMERS_VIEW)
        customer = self._repository.get(customer_id)
        if customer is None:
            raise ValueError("Cliente não encontrado.")
        return customer

    def create(self, session: AuthenticatedSession, data: CustomerInput) -> Customer:
        require_permission(session, Permission.CUSTOMERS_CREATE)
        if (data.credit.enabled or data.credit.credit_limit) and Permission.CREDIT_ENABLE not in session.permissions: raise PermissionError("Sem permissão para habilitar fiado.")
        self._validate_age_confirmation(data)
        customer = self._repository.create(data)
        self._audit.record(user=session.user, action="cliente_criado", module="clientes", affected_id=customer.id)
        return customer

    def update(self, session: AuthenticatedSession, customer_id: str, data: CustomerInput) -> Customer:
        require_permission(session, Permission.CUSTOMERS_EDIT)
        current=self._repository.get(customer_id)
        if current and (data.credit.enabled!=current.credit.enabled or data.credit.credit_limit!=current.credit.credit_limit) and Permission.CREDIT_ENABLE not in session.permissions: raise PermissionError("Sem permissão para alterar controle de fiado.")
        self._validate_age_confirmation(data)
        customer = self._repository.update(customer_id, data)
        if customer is None:
            raise ValueError("Cliente não encontrado.")
        self._audit.record(user=session.user, action="cliente_alterado", module="clientes", affected_id=customer_id)
        return customer

    def set_active(self, session: AuthenticatedSession, customer_id: str, active: bool, reason: str) -> None:
        require_permission(session, Permission.CUSTOMERS_DEACTIVATE)
        if not reason.strip():
            raise ValueError("Informe o motivo da alteração.")
        if not self._repository.set_active(customer_id, active):
            raise ValueError("Cliente não encontrado.")
        self._audit.record(user=session.user, action="cliente_ativado" if active else "cliente_inativado", module="clientes", affected_id=customer_id, reason=reason)

    def purchase_history(self, session: AuthenticatedSession, customer_id: str) -> list[dict[str, Any]]:
        require_permission(session, Permission.CUSTOMERS_VIEW)
        return self._repository.purchase_history(customer_id)

    @staticmethod
    def _validate_age_confirmation(data: CustomerInput) -> None:
        if data.age_confirmed and data.birth_date:
            today = date.today()
            age = today.year - data.birth_date.year - ((today.month, today.day) < (data.birth_date.month, data.birth_date.day))
            if age < 18:
                raise ValueError("Não é possível confirmar maioridade para cliente menor de 18 anos.")
