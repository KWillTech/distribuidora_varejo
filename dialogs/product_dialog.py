"""Formulário simplificado de produto em uma única tela."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QMessageBox, QSpinBox, QVBoxLayout
from pydantic import ValidationError

from dialogs.catalog_dialogs import parse_money, money_text
from models.catalog import Category, Product, ProductInput


class ProductDialog(QDialog):
    """Expõe somente os campos usados na operação diária da adega."""

    def __init__(self, categories: list[Category], suppliers: list[tuple[str, str]], product: Product | None = None, parent=None) -> None:
        super().__init__(parent)
        self.product = product
        self.setWindowTitle("Editar produto" if product else "Novo produto")
        self.setMinimumWidth(580)
        root = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit(product.name if product else "")
        self.barcode = QLineEdit(product.unit_barcode if product and product.unit_barcode else "")
        self.barcode.setPlaceholderText("8 a 32 dígitos")
        self.category = QComboBox()
        for category in categories:
            self.category.addItem(category.name, category.id)
        if product:
            index = self.category.findData(product.category_id)
            if index >= 0: self.category.setCurrentIndex(index)
        self.minimum_stock = QSpinBox(); self.minimum_stock.setRange(0, 2_000_000_000); self.minimum_stock.setValue(product.minimum_stock if product else 0)
        self.pack_quantity = QSpinBox(); self.pack_quantity.setRange(0, 1000); self.pack_quantity.setSpecialValueText("Sem fardo"); self.pack_quantity.setValue(product.units_per_pack or 0 if product else 0)
        self.product_type = QComboBox(); self.product_type.addItem("Unidade", "unidade"); self.product_type.addItem("Fardo", "fardo")
        if product and (product.package_description or "").casefold() == "fardo": self.product_type.setCurrentIndex(1)
        self.purchase_price = QLineEdit(money_text(product.unit_cost) if product else "0,00")
        self.purchase_price.setPlaceholderText("0,00")
        self.sale_price = QLineEdit(money_text(product.unit_price) if product else "")
        self.sale_price.setPlaceholderText("0,00")
        self.supplier = QComboBox(); self.supplier.addItem("Não informado", None)
        for supplier_id, supplier_name in suppliers: self.supplier.addItem(supplier_name, supplier_id)
        if product and product.main_supplier_id:
            index = self.supplier.findData(product.main_supplier_id)
            if index >= 0: self.supplier.setCurrentIndex(index)
        for label, widget in (("Nome *", self.name), ("Código de barras", self.barcode), ("Categoria *", self.category), ("Estoque mínimo (unidades)", self.minimum_stock), ("Tipo", self.product_type), ("Quantidade por fardo", self.pack_quantity), ("Preço de compra", self.purchase_price), ("Preço de venda *", self.sale_price), ("Fornecedor", self.supplier)):
            form.addRow(label, widget)
        root.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)

    def _internal_code(self) -> str:
        if self.product: return self.product.internal_code
        barcode = self.barcode.text().strip()
        return f"BAR-{barcode}" if barcode else f"PROD-{uuid4().hex[:12].upper()}"

    def data(self) -> ProductInput | None:
        try:
            if self.category.currentIndex() < 0: raise ValueError("Cadastre uma categoria ativa antes do produto.")
            supplier_id = self.supplier.currentData(); kind = self.product_type.currentData()
            previous = self.product; units_per_pack = self.pack_quantity.value() or None
            return ProductInput(
                internal_code=self._internal_code(), unit_barcode=self.barcode.text().strip() or None,
                pack_barcode=previous.pack_barcode if previous else None, name=self.name.text(),
                description=previous.description if previous else None, category_id=str(self.category.currentData()), category_name=self.category.currentText(),
                brand=previous.brand if previous else None, volume=previous.volume if previous else None,
                measurement_unit="FD" if kind == "fardo" else "UN", package_description="Fardo" if kind == "fardo" else "Unidade",
                units_per_pack=units_per_pack,
                unit_cost=parse_money(self.purchase_price.text()) or Decimal("0"), pack_cost=previous.pack_cost if previous and units_per_pack else None,
                unit_price=parse_money(self.sale_price.text(), True), pack_price=previous.pack_price if previous and units_per_pack else None,
                promotional_unit_price=previous.promotional_unit_price if previous else None, promotional_pack_price=previous.promotional_pack_price if previous and units_per_pack else None,
                current_stock_units=previous.current_stock_units if previous else 0, minimum_stock=self.minimum_stock.value(),
                maximum_stock=previous.maximum_stock if previous else None, storage_location=previous.storage_location if previous else None,
                main_supplier_id=str(supplier_id) if supplier_id else None, main_supplier_name=self.supplier.currentText() if supplier_id else None,
                initial_lot=previous.initial_lot if previous else None, expiration_date=previous.expiration_date if previous else None,
                photo_path=previous.photo_path if previous else None, active=previous.active if previous else True,
            )
        except (ValidationError, ValueError) as exc:
            message = exc.errors()[0]["msg"] if isinstance(exc, ValidationError) else str(exc)
            QMessageBox.warning(self, "Produto inválido", message); return None

    def accept(self) -> None:
        if self.data() is not None: super().accept()
