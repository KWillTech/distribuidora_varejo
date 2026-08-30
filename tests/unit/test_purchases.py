"""Testes de totais, recebimento e integração da compra."""

from datetime import date
from decimal import Decimal

import pytest

from models.auth import AuthenticatedSession, Permission, ProfileCode, User
from models.catalog import PackageType
from models.purchase import Purchase, PurchaseInput, PurchaseItem, PurchasePaymentMethod, PurchaseStatus
from services.purchases import PurchaseService


def purchase_input(**changes) -> PurchaseInput:
    item = PurchaseItem(product_id="p1", product_name="Cerveja", package_type=PackageType.PACK, quantity=10, units_per_pack=12, cost_per_package=Decimal("36.00"), lot_code="L1")
    values = {"supplier_id": "f1", "supplier_name": "Fornecedor", "invoice_number": "123", "items": [item], "payment_method": PurchasePaymentMethod.CREDIT, "installment_days": [7, 14, 21]} | changes
    return PurchaseInput(**values)


def session() -> AuthenticatedSession:
    user = User(id="u1", username="estoque", email="estoque@example.com", full_name="Pessoa Estoquista", profile_code=ProfileCode.STOCK)
    return AuthenticatedSession(session_id="s1", user=user, permissions={Permission.PURCHASES_CREATE, Permission.PURCHASES_CANCEL, Permission.STOCK_ADJUST})


class FakePurchases:
    def __init__(self): self.payable = None; self.conflicts = []
    def create_pending(self, data, user): return Purchase(id="c1", number="CP-00000001", status=PurchaseStatus.PENDING, created_by=user.username, **data.model_dump())
    def mark_received(self, purchase_id):
        result = self.current.model_copy(update={"status": PurchaseStatus.RECEIVED}); return result
    def create_payable(self, purchase): self.payable = purchase
    def cancel_payable(self, purchase_id): self.payable = None
    def get(self, purchase_id): return self.current if self.current.id == purchase_id else None
    def get_by_number(self, number): return self.current if self.current.number == number.strip().upper() else None
    def confirm_receipt(self, purchase_id, invoice_numbers):
        self.current = self.current.model_copy(update={"status": PurchaseStatus.RECEIPT_CONFIRMED, "invoice_number": ", ".join(invoice_numbers), "invoice_numbers": invoice_numbers}); return self.current
    def invoice_conflicts(self, supplier_id, invoice_numbers, exclude_purchase_id): return self.conflicts
    def set_expiration_dates(self, purchase_id, expiration_dates):
        items=[item.model_copy(update={"expiration_date":expiration_dates[item.product_id]}) for item in self.current.items]; self.current=self.current.model_copy(update={"items":items}); return self.current


class FakeProducts:
    def __init__(self): self.costs = []
    def update_unit_cost(self, product_id, cost): self.costs.append((product_id, cost))


class FakeStock:
    def __init__(self): self.movements = []
    def move(self, session, movement): self.movements.append(movement)


class FakeAudit:
    def __init__(self): self.actions = []
    def record(self, **kwargs): self.actions.append(kwargs["action"])


def test_purchase_totals_and_pack_conversion() -> None:
    data = purchase_input()
    assert data.items[0].converted_units == 120
    assert data.items[0].unit_cost == Decimal("3.00")
    assert data.subtotal == Decimal("360.00")
    assert data.total == Decimal("360.00")


def test_credit_purchase_requires_installment_days() -> None:
    with pytest.raises(ValueError, match="prazos"):
        purchase_input(installment_days=[])


def test_receipt_moves_stock_updates_cost_and_payable() -> None:
    purchases = FakePurchases(); products = FakeProducts(); stock = FakeStock(); audit = FakeAudit(); data = purchase_input()
    purchases.current = purchases.create_pending(data, session().user)
    # O serviço cria novamente; o fake usa os mesmos dados como compra atual.
    original_create = purchases.create_pending
    def create(data_value, user_value):
        purchases.current = original_create(data_value, user_value); return purchases.current
    purchases.create_pending = create
    result = PurchaseService(purchases, products, stock, audit).receive(session(), data)
    assert result.status == PurchaseStatus.RECEIVED
    assert stock.movements[0].informed_quantity == 10
    assert stock.movements[0].units_per_pack == 12
    assert products.costs == [("p1", Decimal("3.00"))]
    assert purchases.payable.id == result.id
    assert audit.actions == ["compra_recebida"]

def test_confirmation_does_not_move_stock_until_invoice_entry() -> None:
    purchases = FakePurchases(); products = FakeProducts(); stock = FakeStock(); audit = FakeAudit(); data = purchase_input()
    purchases.current = purchases.create_pending(data, session().user).model_copy(update={"status": PurchaseStatus.SENT})
    service = PurchaseService(purchases, products, stock, audit)
    confirmed = service.confirm_receipt(session(), "c1", ["NF-10", "NF-11"])
    assert confirmed.status == PurchaseStatus.RECEIPT_CONFIRMED
    assert confirmed.invoice_numbers == ["NF-10", "NF-11"]
    assert stock.movements == []
    completed = service.post_invoice_entry(session(), "c1", {"p1": date(2027, 12, 31)})
    assert completed.status == PurchaseStatus.RECEIVED
    assert len(stock.movements) == 1
    assert stock.movements[0].expiration_date == date(2027, 12, 31)
    assert stock.movements[0].lot_code == "L1"

def test_confirmation_rejects_duplicate_invoice_for_same_supplier() -> None:
    purchases = FakePurchases(); purchases.current = purchases.create_pending(purchase_input(), session().user).model_copy(update={"status": PurchaseStatus.SENT}); purchases.conflicts = [("NF-10", "CP-00000009")]
    service = PurchaseService(purchases, FakeProducts(), FakeStock(), FakeAudit())
    with pytest.raises(ValueError, match="NF-10.*CP-00000009"):
        service.confirm_receipt(session(), "c1", ["NF-10"])
