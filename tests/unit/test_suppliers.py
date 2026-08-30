"""Testes do domínio e autorização de fornecedores."""

import pytest
from pydantic import ValidationError

from models.auth import AuthenticatedSession, Permission, ProfileCode, User
from models.supplier import Supplier, SupplierInput, SupplierPage, valid_cnpj
from services.rbac import AuthorizationError
from services.suppliers import SupplierService


class FakeRepository:
    def __init__(self): self.created = None
    def create(self, data): self.created = Supplier(id="f1", **data.model_dump()); return self.created
    def list_page(self, **kwargs): return SupplierPage(items=[], total=0, page=kwargs["page"], page_size=kwargs["page_size"])


class FakeAudit:
    def __init__(self): self.actions = []
    def record(self, **kwargs): self.actions.append(kwargs["action"])


def session(*permissions: Permission) -> AuthenticatedSession:
    user = User(id="u1", username="gerente", email="gerente@example.com", full_name="Pessoa Gerente", profile_code=ProfileCode.MANAGER)
    return AuthenticatedSession(session_id="s1", user=user, permissions=set(permissions))


def supplier_data() -> SupplierInput:
    return SupplierInput(legal_name="Fornecedor Teste Ltda", trade_name="Fornecedor Teste", document="04.252.011/0001-10", phone="(11) 99999-9999")


def test_cnpj_is_validated_and_normalized() -> None:
    assert valid_cnpj("04252011000110") is True
    data = supplier_data()
    assert data.document == "04252011000110"
    assert data.phone == "11999999999"
    with pytest.raises(ValidationError, match="CPF ou CNPJ inválido"):
        SupplierInput(legal_name="Inválido", document="11.111.111/1111-11")


def test_create_requires_permission_and_audits() -> None:
    repository = FakeRepository(); audit = FakeAudit(); service = SupplierService(repository, audit)
    with pytest.raises(AuthorizationError): service.create(session(), supplier_data())
    created = service.create(session(Permission.SUPPLIERS_CREATE), supplier_data())
    assert created.id == "f1"
    assert audit.actions == ["fornecedor_criado"]


def test_pagination_is_validated() -> None:
    service = SupplierService(FakeRepository(), FakeAudit())
    with pytest.raises(ValueError, match="Paginação"):
        service.list_page(session(Permission.SUPPLIERS_VIEW), page=0, page_size=20)

