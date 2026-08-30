"""Regras monetárias e conversão do PDV."""
from decimal import Decimal
import pytest
from models.auth import AuthenticatedSession,Permission,ProfileCode,User
from models.catalog import PackageType
from models.sale import PaymentMethod,SaleInput,SaleItem,SalePayment
from services.sales import SaleService

def item(): return SaleItem(product_id="p1",product_name="Cerveja",package_type=PackageType.PACK,quantity=2,units_per_pack=12,unit_price=Decimal("36.00"))

def test_pack_sale_and_mixed_payment():
    sale=SaleInput(items=[item()],total_discount=Decimal("2.00"),surcharge=Decimal("1.00"),payments=[SalePayment(method=PaymentMethod.PIX,amount=Decimal("40.00")),SalePayment(method=PaymentMethod.DEBIT,amount=Decimal("31.00"))])
    assert sale.items[0].converted_units==24
    assert sale.total==Decimal("71.00")
    assert sale.change==Decimal("0.00")

def test_change_requires_cash():
    with pytest.raises(ValueError,match="troco"):
        SaleInput(items=[item()],payments=[SalePayment(method=PaymentMethod.PIX,amount=Decimal("80.00"))])

def test_total_discount_cannot_exceed_cart():
    with pytest.raises(ValueError,match="desconto total"):
        SaleInput(items=[item()],total_discount=Decimal("73.00"),surcharge=Decimal("2.00"),payments=[SalePayment(method=PaymentMethod.CASH,amount=Decimal("1.00"))])

def test_discount_above_ten_percent_requires_approval():
    user=User(id="u1",username="caixa",email="caixa@example.com",full_name="Pessoa Caixa",profile_code=ProfileCode.CASHIER)
    session=AuthenticatedSession(session_id="s1",user=user,permissions={Permission.POS_ACCESS})
    sale=SaleInput(items=[item()],total_discount=Decimal("8.00"),payments=[SalePayment(method=PaymentMethod.CASH,amount=Decimal("64.00"))])
    with pytest.raises(PermissionError,match="10%"):
        SaleService(None,None,None).finalize(session,sale)
