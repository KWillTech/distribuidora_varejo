"""Teste do formulário de produto com valores Decimal."""

from decimal import Decimal

from dialogs.product_dialog import ProductDialog
from models.catalog import Category
from PySide6.QtWidgets import QTabWidget


def test_product_dialog_returns_decimal_values(qtbot) -> None:
    category = Category(id="c1", name="Cervejas")
    dialog = ProductDialog([category], []); qtbot.addWidget(dialog)
    dialog.name.setText("Cerveja Teste"); dialog.barcode.setText("7891234567890")
    dialog.purchase_price.setText("3,50"); dialog.sale_price.setText("5,25")
    dialog.minimum_stock.setValue(24); dialog.product_type.setCurrentIndex(0); dialog.pack_quantity.setValue(12)
    data = dialog.data()
    assert data is not None
    assert data.unit_cost == Decimal("3.50")
    assert data.unit_price == Decimal("5.25")
    assert data.current_stock_units == 0
    assert data.minimum_stock == 24
    assert data.units_per_pack == 12
    assert data.package_description == "Unidade"
    assert data.internal_code == "BAR-7891234567890"
    assert dialog.findChild(QTabWidget) is None
    assert not hasattr(dialog, "internal_code")
    assert not hasattr(dialog, "pack_barcode")
    assert not hasattr(dialog, "brand")
