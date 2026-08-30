"""Testes das validações e regras do módulo de clientes."""

from datetime import date

import pytest
from pydantic import ValidationError

from models.auth import AuthenticatedSession, Permission, ProfileCode, User
from models.customer import Customer, CustomerInput, CustomerPage, valid_cpf
from services.customers import CustomerService
from services.rbac import AuthorizationError
from repositories.customers import CustomerRepository


class FakeCustomers:
    def __init__(self) -> None:
        self.created = None

    def create(self, data):
        self.created = Customer(id="c1", **data.model_dump())
        return self.created

    def list_page(self, **kwargs):
        return CustomerPage(items=[], total=0, page=kwargs["page"], page_size=kwargs["page_size"])


class FakeAudit:
    def __init__(self) -> None: self.actions = []
    def record(self, **kwargs): self.actions.append(kwargs["action"])


def session(*permissions: Permission) -> AuthenticatedSession:
    user = User(id="u1", username="teste", email="teste@example.com", full_name="Usuário Teste", profile_code=ProfileCode.MANAGER)
    return AuthenticatedSession(session_id="s1", user=user, permissions=set(permissions))


def customer_data(**changes) -> CustomerInput:
    values = {"full_name": "Cliente de Teste", "cpf": "529.982.247-25", "phone": "(11) 99999-9999"} | changes
    return CustomerInput(**values)


def test_cpf_algorithm() -> None:
    assert valid_cpf("52998224725") is True
    assert valid_cpf("11111111111") is False
    with pytest.raises(ValidationError, match="CPF inválido"):
        customer_data(cpf="123.456.789-00")


def test_masks_are_normalized() -> None:
    data = customer_data()
    assert data.cpf == "52998224725"
    assert data.phone == "11999999999"


def test_name_cpf_and_phone_are_optional_and_status_is_accepted() -> None:
    data = CustomerInput(full_name=None, cpf=None, phone=None, active=False)
    assert data.full_name is None
    assert data.cpf is None
    assert data.phone is None
    assert data.active is False


def test_birth_date_is_prepared_as_utc_datetime() -> None:
    data = customer_data(birth_date=date(1990, 5, 20))
    document = CustomerRepository._document(data)
    assert document["data_nascimento"].isoformat() == "1990-05-20T00:00:00+00:00"


def test_minor_cannot_be_marked_as_adult() -> None:
    repository = FakeCustomers(); service = CustomerService(repository, FakeAudit())
    minor_birth = date.today().replace(year=date.today().year - 10)
    with pytest.raises(ValueError, match="menor de 18"):
        service.create(session(Permission.CUSTOMERS_CREATE), customer_data(birth_date=minor_birth, age_confirmed=True))
    assert repository.created is None


def test_create_requires_permission_and_audits() -> None:
    repository = FakeCustomers(); audit = FakeAudit(); service = CustomerService(repository, audit)
    with pytest.raises(AuthorizationError):
        service.create(session(), customer_data())
    created = service.create(session(Permission.CUSTOMERS_CREATE), customer_data())
    assert created.id == "c1"
    assert audit.actions == ["cliente_criado"]


def test_invalid_page_is_rejected_before_repository() -> None:
    service = CustomerService(FakeCustomers(), FakeAudit())
    with pytest.raises(ValueError, match="Paginação"):
        service.list_page(session(Permission.CUSTOMERS_VIEW), page=0)
