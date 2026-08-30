"""Teste do formulário de compra."""

from datetime import date
from decimal import Decimal

from dialogs.purchase_dialog import PurchaseDialog, PurchaseItemDialog
from models.catalog import PackageType, Product
from models.purchase import PurchaseItem, PurchasePaymentMethod


def test_purchase_dialog_builds_decimal_total(qtbot) -> None:
    product = Product(id="p1", internal_code="CER-001", name="Cerveja", category_id="c1", category_name="Cervejas", unit_price=Decimal("5.00"), units_per_pack=12)
    dialog = PurchaseDialog([("f1", "Fornecedor", "11999999999")], [product]); qtbot.addWidget(dialog)
    dialog.items = [PurchaseItem(product_id="p1", product_name="Cerveja", package_type=PackageType.PACK, quantity=2, units_per_pack=12, cost_per_package=Decimal("36.00"))]
    dialog.payment.setCurrentIndex(dialog.payment.findData(PurchasePaymentMethod.CREDIT)); dialog.terms.setText("7/14/21"); dialog._refresh()
    data = dialog.data()
    assert data is not None
    assert data.total == Decimal("72.00")
    assert data.items[0].converted_units == 24
    assert data.installment_days == [7, 14, 21]

def test_product_can_be_typed_and_fills_category(qtbot) -> None:
    product = Product(id="p1", internal_code="BAL-001", name="Bala", category_id="c1", category_name="Doces", unit_cost=Decimal("5.00"), unit_price=Decimal("7.00"))
    dialog = PurchaseItemDialog([product]); qtbot.addWidget(dialog)
    dialog.product.setEditText("bala")
    assert dialog.category.text() == "Doces"
    assert dialog.cost.text() == "5,00"
    assert dialog.data().product_id == "p1"
