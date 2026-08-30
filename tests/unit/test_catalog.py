"""Testes de categorias, produtos e regras monetárias."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from models.auth import AuthenticatedSession, Permission, ProfileCode, User
from models.catalog import INITIAL_CATEGORIES, Product, ProductInput
from services.catalog import CatalogService
from services.rbac import AuthorizationError


def product_data(**changes) -> ProductInput:
    values = {"internal_code": "cer-001", "name": "Cerveja Teste", "category_id": "c1", "category_name": "Cervejas", "unit_cost": Decimal("3.50"), "unit_price": Decimal("5.25")} | changes
    return ProductInput(**values)


def session(*permissions: Permission) -> AuthenticatedSession:
    user = User(id="u1", username="gerente", email="gerente@example.com", full_name="Pessoa Gerente", profile_code=ProfileCode.MANAGER)
    return AuthenticatedSession(session_id="s1", user=user, permissions=set(permissions))


def test_initial_categories_are_complete() -> None:
    assert len(INITIAL_CATEGORIES) == 15
    assert {"Cervejas", "Gelo", "Combos", "Outros"}.issubset(INITIAL_CATEGORIES)


def test_decimal_margin_and_stock_display() -> None:
    data = product_data(units_per_pack=12, pack_price=Decimal("55.00"), current_stock_units=93)
    assert data.internal_code == "CER-001"
    assert data.unit_margin_percent == Decimal("50.00")
    product = Product(id="p1", **data.model_dump())
    assert product.stock_display == "7 fardo(s) e 9 un."


def test_pack_fields_require_composition() -> None:
    with pytest.raises(ValidationError, match="unidades por fardo"):
        product_data(pack_price=Decimal("50.00"))


def test_barcodes_must_differ() -> None:
    with pytest.raises(ValidationError, match="devem ser diferentes"):
        product_data(unit_barcode="7891234567890", pack_barcode="7891234567890", units_per_pack=12)


class EmptyCategories: pass
class EmptyProducts:
    def list_page(self, **kwargs): raise AssertionError("não deveria consultar")
class EmptyAudit: pass


def test_product_list_requires_permission() -> None:
    service = CatalogService(EmptyCategories(), EmptyProducts(), EmptyAudit())
    with pytest.raises(AuthorizationError): service.list_products(session(), page=1, page_size=20)

