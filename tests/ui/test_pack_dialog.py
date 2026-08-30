"""Teste da configuração separada de fardo."""

from decimal import Decimal

from dialogs.pack_dialog import PackConfigurationDialog
from models.catalog import Product


def test_pack_dialog_builds_configuration(qtbot) -> None:
    product = Product(id="p1", internal_code="CER-001", name="Cerveja", category_id="c1", category_name="Cervejas", unit_price=Decimal("5.00"))
    dialog = PackConfigurationDialog(product); qtbot.addWidget(dialog)
    dialog.units.setValue(12); dialog.barcode.setText("7891234567890"); dialog.price.setText("54,00")
    data = dialog.data()
    assert data is not None
    assert data.units_per_pack == 12
    assert data.pack_price == Decimal("54.00")

