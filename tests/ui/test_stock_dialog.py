"""Teste do formulário de movimentação de estoque."""

from decimal import Decimal

from dialogs.stock_dialogs import StockMovementDialog
from models.catalog import PackageType, Product


def test_stock_dialog_converts_pack_configuration(qtbot) -> None:
    product = Product(id="p1", internal_code="CER-001", name="Cerveja", category_id="c1", category_name="Cervejas", unit_barcode="7891234567890", pack_barcode="7891234567891", unit_price=Decimal("5.00"), units_per_pack=12, pack_price=Decimal("54.00"), current_stock_units=100)
    dialog = StockMovementDialog([product]); qtbot.addWidget(dialog)
    dialog.barcode.setText("7891234567891"); dialog._barcode_changed(); dialog.quantity.setValue(2); dialog.nfe_number.setText("NF-123")
    data = dialog.data()
    assert data is not None
    assert data.package_type == PackageType.PACK
    assert data.converted_units == 24
    assert data.product_id == "p1"
    assert data.reason == "Entrada"
    assert data.related_document == "NF-123"
    assert not hasattr(dialog, "direction")
    assert not hasattr(dialog, "reason")


def test_pack_option_is_disabled_without_composition(qtbot) -> None:
    product = Product(id="p2", internal_code="AGU-001", name="Água", category_id="c2", category_name="Águas", unit_price=Decimal("3.00"), current_stock_units=20)
    dialog = StockMovementDialog([product]); qtbot.addWidget(dialog)
    assert dialog.package.model().item(1).isEnabled() is False
    assert dialog.package.currentData() == PackageType.UNIT
