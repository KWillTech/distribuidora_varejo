"""Validação do fluxo de pedidos e entregas."""
from decimal import Decimal
import pytest
from models.order import OrderInput,OrderStatus
from services.orders import TRANSITIONS

def test_delivery_order_validates_required_data():
    order=OrderInput(customer_name="Cliente Teste",phone="11999999999",address="Rua Teste, 10",products="2 águas",volumes=1,delivery_fee=Decimal("5"),payment_method="Pix")
    assert order.delivery_fee==Decimal("5")

def test_delivery_status_flow_is_controlled():
    assert OrderStatus.PAID in TRANSITIONS[OrderStatus.AWAITING_PAYMENT]
    assert OrderStatus.DELIVERED not in TRANSITIONS[OrderStatus.AWAITING_PAYMENT]
    assert OrderStatus.DELIVERED in TRANSITIONS[OrderStatus.OUT_FOR_DELIVERY]

def test_delivery_requires_at_least_one_volume():
    with pytest.raises(ValueError):
        OrderInput(customer_name="Cliente Teste",phone="11999999999",address="Rua Teste, 10",products="Água",volumes=0,payment_method="Pix")

def test_delivery_rejects_invalid_phone():
    with pytest.raises(ValueError,match="telefone"):
        OrderInput(customer_name="Cliente Teste",phone="12345678",address="Rua Teste, 10",products="Água",volumes=1,payment_method="Pix")
