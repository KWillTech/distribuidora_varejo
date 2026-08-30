"""Regras monetárias do financeiro."""
from datetime import date
from decimal import Decimal
import pytest
from models.finance import FinancialEntry,FinancialInput,FinancialKind,PaymentInput

def test_financial_balance_uses_decimal():
    entry=FinancialEntry(id="f1",kind=FinancialKind.PAYABLE,description="Compra",original_amount=Decimal("100.00"),paid_amount=Decimal("35.25"),due_date=date.today())
    assert entry.balance==Decimal("64.75")

def test_financial_entry_requires_positive_amount():
    with pytest.raises(ValueError):FinancialInput(kind=FinancialKind.EXPENSE,description="Energia",category="Fixas",amount=Decimal("0"),due_date=date.today())

def test_payment_requires_positive_amount():
    with pytest.raises(ValueError):PaymentInput(amount=Decimal("0"),payment_date=date.today(),payment_method="Pix")

def test_disabled_recurrence_always_creates_one_entry():
    entry=FinancialInput(kind=FinancialKind.EXPENSE,description="Internet",category="Fixas",amount=Decimal("100"),due_date=date.today(),recurring=False,recurrence_count=12)
    assert entry.recurrence_count==1
