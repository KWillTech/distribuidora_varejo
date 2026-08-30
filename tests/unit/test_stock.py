"""Testes de conversão, autorização e persistência atômica do estoque."""

from unittest.mock import MagicMock

import pytest

from models.auth import AuthenticatedSession, Permission, ProfileCode, User
from models.catalog import PackageType
from models.stock import InventoryRequest, StockMovementRequest, StockMovementType
from repositories.stock import StockConflictError, StockRepository
from services.stock import StockService


def user(profile=ProfileCode.STOCK) -> User:
    return User(id="u1", username="estoque", email="estoque@example.com", full_name="Pessoa Estoquista", profile_code=profile)


def request(**changes) -> StockMovementRequest:
    values = {"product_id": "p1", "product_name": "Cerveja", "movement_type": StockMovementType.DAMAGE, "package_type": PackageType.PACK, "informed_quantity": 2, "units_per_pack": 12, "reason": "Produtos avariados"} | changes
    return StockMovementRequest(**values)


def fake_database():
    database = MagicMock(); products = MagicMock(); movements = MagicMock(); lots = MagicMock()
    collections = {"produtos": products, "movimentacoes_estoque": movements, "lotes": lots}
    database.__getitem__.side_effect = collections.__getitem__
    movements.insert_one.return_value.inserted_id = "m1"
    return database, products, movements, lots


def test_pack_exit_is_atomic_and_records_balances() -> None:
    database, products, movements, _ = fake_database(); products.find_one_and_update.return_value = {"_id": "p1", "estoque_atual_unidades": 93}
    result = StockRepository(database).apply(request(), user())
    query = products.find_one_and_update.call_args.args[0]
    update = products.find_one_and_update.call_args.args[1]
    assert query["estoque_atual_unidades"] == {"$gte": 24}
    assert update["$inc"]["estoque_atual_unidades"] == -24
    assert result.balance_before == 93
    assert result.balance_after == 69
    assert movements.insert_one.call_count == 1


def test_insufficient_stock_does_not_record_movement() -> None:
    database, products, movements, _ = fake_database(); products.find_one_and_update.return_value = None
    with pytest.raises(StockConflictError): StockRepository(database).apply(request(), user())
    movements.insert_one.assert_not_called()


def test_non_admin_cannot_authorize_negative_stock() -> None:
    repository = MagicMock(); audit = MagicMock(); service = StockService(repository, audit)
    session = AuthenticatedSession(session_id="s1", user=user(), permissions={Permission.STOCK_ADJUST})
    with pytest.raises(PermissionError, match="administrador"):
        service.move(session, request(), allow_negative=True)
    repository.apply.assert_not_called()


def test_manual_adjustment_requires_direction() -> None:
    with pytest.raises(ValueError, match="direção"):
        request(movement_type=StockMovementType.MANUAL_ADJUSTMENT, package_type=PackageType.UNIT, units_per_pack=None)


def test_inventory_records_counted_balance_and_difference() -> None:
    database, products, movements, _ = fake_database(); products.find_one_and_update.return_value = {"_id": "p1", "estoque_atual_unidades": 100}
    result = StockRepository(database).inventory(InventoryRequest(product_id="p1", product_name="Cerveja", counted_units=93, reason="Contagem mensal"), user())
    assert result.movement_type == StockMovementType.INVENTORY
    assert result.converted_units == -7
    assert result.balance_before == 100
    assert result.balance_after == 93
