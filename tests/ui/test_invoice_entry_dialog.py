"""Teste do preenchimento obrigatório das validades da NF-e."""
from datetime import date
from decimal import Decimal
from dialogs.invoice_entry_dialog import InvoiceExpiryDialog
from models.catalog import PackageType
from models.purchase import Purchase,PurchaseItem,PurchasePaymentMethod,PurchaseStatus

def test_expiry_dialog_has_one_date_for_each_product(qtbot):
    items=[PurchaseItem(product_id="p1",product_name="Cerveja",package_type=PackageType.UNIT,quantity=1,cost_per_package=Decimal("5")),PurchaseItem(product_id="p2",product_name="Suco",package_type=PackageType.UNIT,quantity=2,cost_per_package=Decimal("4"))]
    purchase=Purchase(id="c1",number="CP-1",supplier_id="f1",supplier_name="Fornecedor",items=items,payment_method=PurchasePaymentMethod.PIX,status=PurchaseStatus.RECEIPT_CONFIRMED,created_by="admin")
    dialog=InvoiceExpiryDialog(purchase); qtbot.addWidget(dialog); values=dialog.expiration_dates()
    assert set(values)=={"p1","p2"}
    assert all(value>=date.today() for value in values.values())
