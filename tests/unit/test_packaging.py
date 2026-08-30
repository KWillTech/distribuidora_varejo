"""Testes das regras de unidade e fardo."""

from decimal import Decimal

import pytest

from models.auth import AuthenticatedSession, Permission, ProfileCode, User
from models.catalog import PackageType, Product
from models.packaging import SalePackageRequest
from services.packaging import InsufficientStockError, PackagingService


class EmptyProducts: pass
class EmptyAudit: pass


def session() -> AuthenticatedSession:
    user = User(id="u1", username="caixa", email="caixa@example.com", full_name="Pessoa Caixa", profile_code=ProfileCode.CASHIER)
    return AuthenticatedSession(session_id="s1", user=user, permissions={Permission.PRODUCTS_VIEW})


def product(**changes) -> Product:
    values = {"id": "p1", "internal_code": "CER-001", "name": "Cerveja", "category_id": "c1", "category_name": "Cervejas", "unit_cost": Decimal("3.00"), "unit_price": Decimal("5.00"), "pack_price": Decimal("54.00"), "units_per_pack": 12, "current_stock_units": 93} | changes
    return Product(**values)


def test_two_packs_and_three_units_convert_to_27() -> None:
    service = PackagingService(EmptyProducts(), EmptyAudit()); current = product()
    packs = service.quote(session(), SalePackageRequest(product=current, package_type=PackageType.PACK, quantity=2))
    units = service.quote(session(), SalePackageRequest(product=current.model_copy(update={"current_stock_units": packs.stock_after_units}), package_type=PackageType.UNIT, quantity=3))
    assert packs.converted_units == 24
    assert units.converted_units == 3
    assert units.stock_after_units == 66


def test_pack_uses_independent_promotional_price() -> None:
    service = PackagingService(EmptyProducts(), EmptyAudit()); current = product(promotional_pack_price=Decimal("50.00"))
    quote = service.quote(session(), SalePackageRequest(product=current, package_type=PackageType.PACK, quantity=2))
    assert quote.unit_package_price == Decimal("50.00")
    assert quote.total == Decimal("100.00")


def test_pack_without_enough_units_is_rejected() -> None:
    service = PackagingService(EmptyProducts(), EmptyAudit())
    with pytest.raises(InsufficientStockError):
        service.quote(session(), SalePackageRequest(product=product(current_stock_units=11), package_type=PackageType.PACK, quantity=1))


def test_pack_return_restores_all_units() -> None:
    assert PackagingService.returned_units(product(), PackageType.PACK, 2) == 24
    assert PackagingService.returned_units(product(), PackageType.UNIT, 3) == 3


def test_product_without_pack_cannot_be_sold_as_pack() -> None:
    service = PackagingService(EmptyProducts(), EmptyAudit())
    with pytest.raises(ValueError, match="não configurado"):
        service.quote(session(), SalePackageRequest(product=product(units_per_pack=None, pack_price=None), package_type=PackageType.PACK, quantity=1))


def test_mixed_cart_uses_accumulated_stock() -> None:
    service = PackagingService(EmptyProducts(), EmptyAudit()); current = product(current_stock_units=93)
    quotes = service.quote_cart(session(), [
        SalePackageRequest(product=current, package_type=PackageType.PACK, quantity=7),
        SalePackageRequest(product=current, package_type=PackageType.UNIT, quantity=9),
    ])
    assert quotes[-1].stock_after_units == 0
    with pytest.raises(InsufficientStockError):
        service.quote_cart(session(), [
            SalePackageRequest(product=current, package_type=PackageType.PACK, quantity=7),
            SalePackageRequest(product=current, package_type=PackageType.UNIT, quantity=10),
        ])
