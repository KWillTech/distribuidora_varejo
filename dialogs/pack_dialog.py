"""Configuração separada de venda por fardo."""

from decimal import Decimal

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QMessageBox, QSpinBox
from pydantic import ValidationError

from dialogs.catalog_dialogs import money_text, parse_money
from models.catalog import Product
from models.packaging import PackConfiguration


class PackConfigurationDialog(QDialog):
    def __init__(self, product: Product, parent=None) -> None:
        super().__init__(parent); self.setWindowTitle(f"Venda por fardo — {product.name}"); self.setMinimumWidth(460)
        form = QFormLayout(self); self.units = QSpinBox(); self.units.setRange(0, 1000); self.units.setSpecialValueText("Venda por fardo desativada"); self.units.setValue(product.units_per_pack or 0)
        self.barcode = QLineEdit(product.pack_barcode or ""); self.barcode.setPlaceholderText("Código exclusivo do fardo")
        self.price = QLineEdit(money_text(product.pack_price)); self.promotion = QLineEdit(money_text(product.promotional_pack_price))
        form.addRow("Unidades por fardo", self.units); form.addRow("Código de barras do fardo", self.barcode); form.addRow("Preço de venda do fardo", self.price); form.addRow("Preço promocional", self.promotion)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); form.addRow(buttons)
    def data(self) -> PackConfiguration | None:
        try:
            enabled = self.units.value() > 0
            return PackConfiguration(units_per_pack=self.units.value() if enabled else None, pack_barcode=self.barcode.text().strip() or None if enabled else None, pack_price=parse_money(self.price.text()) if enabled else None, promotional_pack_price=parse_money(self.promotion.text()) if enabled else None)
        except (ValidationError, ValueError) as exc:
            message = exc.errors()[0]["msg"] if isinstance(exc, ValidationError) else str(exc); QMessageBox.warning(self, "Configuração inválida", message); return None
    def accept(self) -> None:
        if self.data() is not None: super().accept()

