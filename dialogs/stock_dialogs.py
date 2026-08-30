"""Diálogos de movimentação e inventário de estoque."""

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QCheckBox, QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QMessageBox, QSpinBox
from pydantic import ValidationError

from models.catalog import PackageType, Product
from models.stock import InventoryRequest, StockMovementRequest, StockMovementType


MOVEMENT_LABELS = {
    StockMovementType.PURCHASE_ENTRY: "Entrada", StockMovementType.RETURN_ENTRY: "Devolução",
    StockMovementType.EXCHANGE_ENTRY: "Troca - entrada", StockMovementType.EXCHANGE_EXIT: "Troca - saída",
    StockMovementType.LOSS: "Perda", StockMovementType.DAMAGE: "Avaria", StockMovementType.EXPIRATION: "Vencimento",
    StockMovementType.INTERNAL_USE: "Uso interno", StockMovementType.BONUS: "Bonificação",
}


class StockMovementDialog(QDialog):
    def __init__(self, products: list[Product], parent=None) -> None:
        super().__init__(parent); self.products = products; self.setWindowTitle("Movimentação de estoque"); self.setMinimumWidth(520); form = QFormLayout(self)
        self.barcode = QLineEdit(); self.barcode.setPlaceholderText("Leia ou digite o código de barras"); self.barcode.editingFinished.connect(self._barcode_changed)
        self.product = QComboBox()
        for item in products: self.product.addItem(f"{item.name} — saldo {item.current_stock_units} un.", item)
        self.product.currentIndexChanged.connect(self._product_changed)
        self.movement_type = QComboBox()
        for movement, label in MOVEMENT_LABELS.items(): self.movement_type.addItem(label, movement)
        self.package = QComboBox(); self.package.addItem("Unidade", PackageType.UNIT); self.package.addItem("Fardo", PackageType.PACK)
        self.quantity = QSpinBox(); self.quantity.setRange(1, 1_000_000_000)
        self.nfe_number = QLineEdit(); self.lot = QLineEdit()
        self.has_expiry = QCheckBox("Informar validade do lote"); self.expiry = QDateEdit(); self.expiry.setCalendarPopup(True); self.expiry.setDisplayFormat("dd/MM/yyyy"); self.expiry.setDate(QDate.currentDate().addYears(1)); self.expiry.setEnabled(False); self.has_expiry.toggled.connect(self.expiry.setEnabled)
        for label, widget in (("Código de barras", self.barcode), ("Produto", self.product), ("Movimentação", self.movement_type), ("Movimentar por", self.package), ("Quantidade", self.quantity), ("Número da NF-e", self.nfe_number), ("Lote", self.lot), ("", self.has_expiry), ("Validade", self.expiry)): form.addRow(label, widget)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); form.addRow(buttons)
        self._product_changed()
    def _product_changed(self) -> None:
        product = self.product.currentData(); pack_item = self.package.model().item(1)
        if pack_item is not None: pack_item.setEnabled(bool(product and product.units_per_pack))
        if product and not product.units_per_pack and self.package.currentIndex() == 1: self.package.setCurrentIndex(0)
    def _barcode_changed(self) -> None:
        barcode = self.barcode.text().strip()
        if not barcode: return
        for index, product in enumerate(self.products):
            if barcode == product.unit_barcode:
                self.product.setCurrentIndex(index); self._product_changed(); self.package.setCurrentIndex(0); return
            if barcode == product.pack_barcode:
                self.product.setCurrentIndex(index); self._product_changed(); self.package.setCurrentIndex(1); return
        QMessageBox.warning(self, "Código não encontrado", "Nenhum produto ativo possui este código de barras.")
    def data(self) -> StockMovementRequest | None:
        product = self.product.currentData()
        if product is None: QMessageBox.warning(self, "Estoque", "Nenhum produto ativo disponível."); return None
        movement_type = self.movement_type.currentData(); automatic_reason = MOVEMENT_LABELS[movement_type]
        try: return StockMovementRequest(product_id=product.id or "", product_name=product.name, movement_type=movement_type, package_type=self.package.currentData(), informed_quantity=self.quantity.value(), units_per_pack=product.units_per_pack, reason=automatic_reason, related_document=self.nfe_number.text() or None, lot_code=self.lot.text() or None, expiration_date=self.expiry.date().toPython() if self.has_expiry.isChecked() else None)
        except ValidationError as exc: QMessageBox.warning(self, "Movimentação inválida", exc.errors()[0]["msg"]); return None
    def accept(self) -> None:
        if self.data(): super().accept()


class InventoryDialog(QDialog):
    def __init__(self, products: list[Product], parent=None) -> None:
        super().__init__(parent); self.setWindowTitle("Inventário"); form = QFormLayout(self); self.product = QComboBox()
        for item in products: self.product.addItem(f"{item.name} — sistema {item.current_stock_units} un.", item)
        self.counted = QSpinBox(); self.counted.setRange(0, 2_000_000_000); self.reason = QLineEdit()
        form.addRow("Produto", self.product); form.addRow("Saldo contado em unidades", self.counted); form.addRow("Motivo", self.reason)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); form.addRow(buttons)
    def data(self) -> InventoryRequest | None:
        product = self.product.currentData()
        if product is None: return None
        try: return InventoryRequest(product_id=product.id or "", product_name=product.name, counted_units=self.counted.value(), reason=self.reason.text())
        except ValidationError as exc: QMessageBox.warning(self, "Inventário inválido", exc.errors()[0]["msg"]); return None
    def accept(self) -> None:
        if self.data(): super().accept()
