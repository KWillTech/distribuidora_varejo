"""Regras do fechamento e movimentação de caixa."""

from decimal import Decimal

import pytest

from models.cash import CashCloseInput, CashMovementInput, CashMovementType, CashRegister
from services.cash import CashService


def test_cash_values_use_decimal():
    movement = CashMovementInput(
        movement_type=CashMovementType.SUPPLY,
        amount=Decimal("10.50"),
        reason="Reforço",
    )
    close = CashCloseInput(counted_amount=Decimal("150.25"))
    assert movement.amount == Decimal("10.50")
    assert close.counted_amount == Decimal("150.25")


def test_cash_movement_must_be_positive():
    with pytest.raises(ValueError):
        CashMovementInput(
            movement_type=CashMovementType.WITHDRAWAL,
            amount=Decimal("0"),
            reason="Teste",
        )


class _CashRepository:
    def __init__(self, amount):
        self.cash = CashRegister(
            id="c1",
            user_id="u1",
            username="caixa",
            opening_amount=amount,
            expected_amount=amount,
        )

    def get_open(self, _user_id):
        return self.cash


class _Session:
    class _User:
        id = "u1"
        username = "caixa"

    user = _User()


def _service_with_balance(amount):
    return CashService(_CashRepository(Decimal(amount)), audit=None)


def test_sale_is_allowed_below_withdrawal_limit():
    service = _service_with_balance("499.99")
    assert service.require_sale_allowed(_Session()).expected_amount == Decimal("499.99")


def test_sale_is_blocked_at_withdrawal_limit():
    service = _service_with_balance("500.00")
    assert service.withdrawal_required(_Session()) is True
    with pytest.raises(ValueError, match="Sangria obrigatória"):
        service.require_sale_allowed(_Session())
