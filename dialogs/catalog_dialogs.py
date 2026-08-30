"""Formulários de categorias e produtos."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QCheckBox, QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QLineEdit, QMessageBox, QPushButton, QSpinBox, QTabWidget, QTextEdit, QVBoxLayout, QWidget
from pydantic import ValidationError

from models.catalog import Category, CategoryInput, Product, ProductInput


def money_text(value: Decimal | None) -> str: return "" if value is None else f"{value:.2f}".replace(".", ",")
def parse_money(value: str, required: bool = False) -> Decimal | None:
    text = value.strip().replace("R$", "").replace(".", "").replace(",", ".")
    if not text:
        if required: raise ValueError("Informe os valores monetários obrigatórios.")
        return None
    try: return Decimal(text).quantize(Decimal("0.01"))
    except InvalidOperation as exc: raise ValueError("Valor monetário inválido.") from exc


class CategoryDialog(QDialog):
    def __init__(self, category: Category | None = None, parent=None) -> None:
        super().__init__(parent); self.setWindowTitle("Editar categoria" if category else "Nova categoria")
        form = QFormLayout(self); self.name = QLineEdit(category.name if category else ""); self.description = QTextEdit(category.description if category and category.description else ""); self.description.setMaximumHeight(90); self.active = QCheckBox("Ativa"); self.active.setChecked(category.active if category else True)
        form.addRow("Nome", self.name); form.addRow("Descrição", self.description); form.addRow("", self.active)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); form.addRow(buttons)
    def data(self) -> CategoryInput | None:
        try: return CategoryInput(name=self.name.text(), description=self.description.toPlainText() or None, active=self.active.isChecked())
        except ValidationError as exc: QMessageBox.warning(self, "Categoria inválida", exc.errors()[0]["msg"]); return None
    def accept(self) -> None:
        if self.data(): super().accept()


class ProductDialog(QDialog):
    def __init__(self, categories: list[Category], suppliers: list[tuple[str, str]], product: Product | None = None, parent=None) -> None:
        super().__init__(parent); self.product = product; self.setWindowTitle("Editar produto" if product else "Novo produto"); self.resize(760, 730)
        root = QVBoxLayout(self); tabs = QTabWidget(); root.addWidget(tabs)
        general = QWidget(); form = QFormLayout(general)
        self.internal_code = QLineEdit(product.internal_code if product else ""); self.name = QLineEdit(product.name if product else "")
        self.unit_barcode = QLineEdit(product.unit_barcode if product and product.unit_barcode else ""); self.pack_barcode = QLineEdit(product.pack_barcode if product and product.pack_barcode else "")
        self.category = QComboBox()
        for item in categories: self.category.addItem(item.name, item.id)
        if product:
            index = self.category.findData(product.category_id)
            if index >= 0: self.category.setCurrentIndex(index)
        self.brand = QLineEdit(product.brand if product and product.brand else ""); self.volume = QLineEdit(product.volume if product and product.volume else "")
        self.measurement = QLineEdit(product.measurement_unit if product else "UN"); self.package_description = QLineEdit(product.package_description if product and product.package_description else "")
        self.description = QTextEdit(product.description if product and product.description else ""); self.description.setMaximumHeight(90)
        self.active = QCheckBox("Produto ativo"); self.active.setChecked(product.active if product else True)
        for label, widget in (("Código interno *", self.internal_code), ("Nome *", self.name), ("Código de barras unidade", self.unit_barcode), ("Código de barras fardo", self.pack_barcode), ("Categoria *", self.category), ("Marca", self.brand), ("Volume", self.volume), ("Unidade de medida", self.measurement), ("Tipo de embalagem", self.package_description), ("Descrição", self.description), ("", self.active)): form.addRow(label, widget)
        tabs.addTab(general, "Identificação")
        commerce = QWidget(); prices = QFormLayout(commerce)
        self.units_per_pack = QSpinBox(); self.units_per_pack.setRange(0, 1000); self.units_per_pack.setSpecialValueText("Sem fardo"); self.units_per_pack.setValue(product.units_per_pack or 0 if product else 0)
        self.unit_cost = QLineEdit(money_text(product.unit_cost) if product else "0,00"); self.pack_cost = QLineEdit(money_text(product.pack_cost) if product else "")
        self.unit_price = QLineEdit(money_text(product.unit_price) if product else ""); self.pack_price = QLineEdit(money_text(product.pack_price) if product else "")
        self.promo_unit = QLineEdit(money_text(product.promotional_unit_price) if product else ""); self.promo_pack = QLineEdit(money_text(product.promotional_pack_price) if product else "")
        for label, widget in (("Unidades por fardo", self.units_per_pack), ("Custo por unidade", self.unit_cost), ("Custo por fardo", self.pack_cost), ("Preço da unidade *", self.unit_price), ("Preço do fardo", self.pack_price), ("Promoção unidade", self.promo_unit), ("Promoção fardo", self.promo_pack)): prices.addRow(label, widget)
        tabs.addTab(commerce, "Preços e fardo")
        stock = QWidget(); stock_form = QFormLayout(stock)
        self.current_stock = QSpinBox(); self.current_stock.setRange(0, 2_000_000_000); self.current_stock.setValue(product.current_stock_units if product else 0); self.current_stock.setEnabled(product is None)
        self.minimum_stock = QSpinBox(); self.minimum_stock.setRange(0, 2_000_000_000); self.minimum_stock.setValue(product.minimum_stock if product else 0)
        self.maximum_stock = QSpinBox(); self.maximum_stock.setRange(0, 2_000_000_000); self.maximum_stock.setSpecialValueText("Não definido"); self.maximum_stock.setValue(product.maximum_stock or 0 if product else 0)
        self.location = QLineEdit(product.storage_location if product and product.storage_location else "")
        self.supplier = QComboBox(); self.supplier.addItem("Não definido", None)
        for supplier_id, supplier_name in suppliers: self.supplier.addItem(supplier_name, supplier_id)
        if product and product.main_supplier_id:
            index = self.supplier.findData(product.main_supplier_id)
            if index >= 0: self.supplier.setCurrentIndex(index)
        self.lot = QLineEdit(product.initial_lot if product and product.initial_lot else "")
        self.has_expiry = QCheckBox("Controlar validade inicial"); self.expiry = QDateEdit(); self.expiry.setCalendarPopup(True); self.expiry.setDisplayFormat("dd/MM/yyyy"); self.expiry.setMinimumDate(QDate.currentDate()); self.expiry.setDate(QDate.currentDate().addYears(1)); self.expiry.setEnabled(False); self.has_expiry.toggled.connect(self.expiry.setEnabled)
        if product and product.expiration_date: self.has_expiry.setChecked(True); self.expiry.setDate(QDate(product.expiration_date.year, product.expiration_date.month, product.expiration_date.day))
        self.photo = QLineEdit(product.photo_path if product and product.photo_path else ""); browse = QPushButton("Selecionar…"); browse.clicked.connect(self._select_photo); photo_row = QHBoxLayout(); photo_row.addWidget(self.photo); photo_row.addWidget(browse)
        for label, widget in (("Estoque inicial em unidades", self.current_stock), ("Estoque mínimo", self.minimum_stock), ("Estoque máximo", self.maximum_stock), ("Localização", self.location), ("Fornecedor principal", self.supplier), ("Lote inicial", self.lot), ("", self.has_expiry), ("Validade", self.expiry)): stock_form.addRow(label, widget)
        stock_form.addRow("Foto", photo_row); tabs.addTab(stock, "Estoque e fornecedor")
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)

    def _select_photo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar foto", "", "Imagens (*.png *.jpg *.jpeg *.webp)")
        if path: self.photo.setText(path)

    def data(self) -> ProductInput | None:
        try:
            if self.category.currentIndex() < 0: raise ValueError("Cadastre uma categoria ativa antes do produto.")
            supplier_id = self.supplier.currentData()
            return ProductInput(
                internal_code=self.internal_code.text(), unit_barcode=self.unit_barcode.text() or None, pack_barcode=self.pack_barcode.text() or None,
                name=self.name.text(), description=self.description.toPlainText() or None, category_id=str(self.category.currentData()), category_name=self.category.currentText(), brand=self.brand.text() or None,
                volume=self.volume.text() or None, measurement_unit=self.measurement.text(), package_description=self.package_description.text() or None,
                units_per_pack=self.units_per_pack.value() or None, unit_cost=parse_money(self.unit_cost.text()) or Decimal("0"), pack_cost=parse_money(self.pack_cost.text()),
                unit_price=parse_money(self.unit_price.text(), True), pack_price=parse_money(self.pack_price.text()), promotional_unit_price=parse_money(self.promo_unit.text()), promotional_pack_price=parse_money(self.promo_pack.text()),
                current_stock_units=self.product.current_stock_units if self.product else self.current_stock.value(), minimum_stock=self.minimum_stock.value(), maximum_stock=self.maximum_stock.value() or None,
                storage_location=self.location.text() or None, main_supplier_id=str(supplier_id) if supplier_id else None, main_supplier_name=self.supplier.currentText() if supplier_id else None,
                initial_lot=self.lot.text() or None, expiration_date=self.expiry.date().toPython() if self.has_expiry.isChecked() else None, photo_path=self.photo.text() or None, active=self.active.isChecked(),
            )
        except (ValidationError, ValueError) as exc:
            message = exc.errors()[0]["msg"] if isinstance(exc, ValidationError) else str(exc); QMessageBox.warning(self, "Produto inválido", message); return None
    def accept(self) -> None:
        if self.data(): super().accept()

