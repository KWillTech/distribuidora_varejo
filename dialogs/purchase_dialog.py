"""Formulário de solicitação de compra e seus itens."""
from decimal import Decimal
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout)
from pydantic import ValidationError
from dialogs.catalog_dialogs import money_text, parse_money
from models.catalog import PackageType, Product
from models.purchase import PurchaseInput, PurchaseItem, PurchasePaymentMethod
from views.dashboard_view import brl

class PurchaseItemDialog(QDialog):
    def __init__(self, products: list[Product], parent=None) -> None:
        super().__init__(parent); self.setWindowTitle("Adicionar produto"); self._products = products; form = QFormLayout(self)
        self.product = QComboBox(); self.product.setEditable(True); self.product.setInsertPolicy(QComboBox.InsertPolicy.NoInsert); self.product.setPlaceholderText("Digite o nome do produto...")
        self.product.completer().setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive); self.product.completer().setFilterMode(Qt.MatchFlag.MatchContains)
        for product in products: self.product.addItem(product.name, product)
        self.category = QLineEdit(); self.category.setReadOnly(True)
        self.package = QComboBox(); self.package.addItem("Unidade", PackageType.UNIT); self.package.addItem("Fardo", PackageType.PACK)
        self.quantity = QSpinBox(); self.quantity.setRange(1, 1_000_000); self.cost = QLineEdit(); self.cost.setPlaceholderText("Preço da unidade ou do fardo")
        self.product.currentIndexChanged.connect(self._product_changed); self.product.editTextChanged.connect(self._product_changed); self.package.currentIndexChanged.connect(self._fill_cost)
        for label, widget in (("Produto", self.product), ("Categoria", self.category), ("Comprar por", self.package), ("Quantidade", self.quantity), ("Preço de compra", self.cost)): form.addRow(label, widget)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel); buttons.button(QDialogButtonBox.StandardButton.Save).setText("Adicionar"); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); form.addRow(buttons); self._product_changed()
    def _selected_product(self) -> Product | None:
        text = self.product.currentText().strip().casefold()
        for index in range(self.product.count()):
            if self.product.itemText(index).casefold() == text: return self.product.itemData(index)
        return None
    def _product_changed(self) -> None:
        product = self._selected_product(); self.category.setText(product.category_name if product else ""); pack_item = self.package.model().item(1)
        if pack_item: pack_item.setEnabled(bool(product and product.units_per_pack))
        if product and not product.units_per_pack: self.package.setCurrentIndex(0)
        self._fill_cost()
    def _fill_cost(self) -> None:
        product = self._selected_product()
        if not product: self.cost.clear(); return
        value = product.calculated_pack_cost if self.package.currentData() == PackageType.PACK else product.unit_cost; self.cost.setText(money_text(value or Decimal("0")))
    def data(self) -> PurchaseItem | None:
        product = self._selected_product()
        if product is None: QMessageBox.warning(self, "Item inválido", "Selecione um produto cadastrado na lista."); return None
        try: return PurchaseItem(product_id=product.id or "", product_name=product.name, package_type=self.package.currentData(), quantity=self.quantity.value(), units_per_pack=product.units_per_pack, cost_per_package=parse_money(self.cost.text(), True))
        except (ValidationError, ValueError) as exc: QMessageBox.warning(self, "Item inválido", exc.errors()[0]["msg"] if isinstance(exc, ValidationError) else str(exc)); return None
    def accept(self) -> None:
        if self.data(): super().accept()

class PurchaseDialog(QDialog):
    def __init__(self, suppliers: list[tuple[str, str, str | None]], products: list[Product], parent=None) -> None:
        super().__init__(parent); self.products = products; self.items: list[PurchaseItem] = []; self.setWindowTitle("Nova solicitação de compra"); self.resize(850, 650); root = QVBoxLayout(self); self.form = QFormLayout()
        self.supplier = QComboBox(); self.supplier.setEditable(True); self.supplier.setInsertPolicy(QComboBox.InsertPolicy.NoInsert); self.supplier.completer().setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive); self.supplier.completer().setFilterMode(Qt.MatchFlag.MatchContains)
        for supplier_id, name, whatsapp in suppliers: self.supplier.addItem(name, (supplier_id, whatsapp))
        self.payment = QComboBox()
        for method, label in ((PurchasePaymentMethod.CASH, "Dinheiro"), (PurchasePaymentMethod.PIX, "Pix"), (PurchasePaymentMethod.BOLETO, "Boleto"), (PurchasePaymentMethod.CREDIT, "A prazo")): self.payment.addItem(label, method)
        self.due = QDateEdit(); self.due.setCalendarPopup(True); self.due.setDisplayFormat("dd/MM/yyyy"); self.due.setDate(QDate.currentDate().addDays(30)); self.terms = QLineEdit(); self.terms.setPlaceholderText("Exemplo: 7/14/21"); self.notes = QTextEdit(); self.notes.setMaximumHeight(70); self.payment.currentIndexChanged.connect(self._payment_changed)
        self.supplier.setPlaceholderText("Digite o nome do fornecedor...")
        for label, widget in (("Fornecedor", self.supplier), ("Pagamento", self.payment), ("Vencimento", self.due), ("Prazos em dias", self.terms), ("Observações", self.notes)): self.form.addRow(label, widget)
        root.addLayout(self.form); self.table = QTableWidget(0, 6); self.table.setHorizontalHeaderLabels(["Produto", "Tipo", "Quantidade", "Unidades", "Preço de compra", "Total"]); self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); root.addWidget(self.table)
        actions = QHBoxLayout(); add = QPushButton("Adicionar produto"); add.clicked.connect(self._add); remove = QPushButton("Remover produto"); remove.clicked.connect(self._remove); actions.addWidget(add); actions.addWidget(remove); actions.addStretch(); self.total_label = QLabel("Total: R$ 0,00"); self.total_label.setObjectName("metricValue"); actions.addWidget(self.total_label); root.addLayout(actions)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel); buttons.button(QDialogButtonBox.StandardButton.Save).setText("Enviar pedido"); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons); self._payment_changed()
    def _payment_changed(self) -> None:
        boleto = self.payment.currentData() == PurchasePaymentMethod.BOLETO; credit = self.payment.currentData() == PurchasePaymentMethod.CREDIT
        for widget, visible in ((self.due, boleto), (self.terms, credit)):
            widget.setVisible(visible); label = self.form.labelForField(widget)
            if label: label.setVisible(visible)
    def _add(self) -> None:
        dialog = PurchaseItemDialog(self.products, self)
        if dialog.exec() == dialog.DialogCode.Accepted:
            item = dialog.data()
            if item: self.items.append(item); self._refresh()
    def _remove(self) -> None:
        row = self.table.currentRow()
        if row >= 0: self.items.pop(row); self._refresh()
    def _refresh(self) -> None:
        self.table.setRowCount(len(self.items))
        for row, item in enumerate(self.items):
            values = (item.product_name, "Fardo" if item.package_type == PackageType.PACK else "Unidade", item.quantity, item.converted_units, brl(item.cost_per_package), brl(item.total))
            for column, value in enumerate(values): self.table.setItem(row, column, QTableWidgetItem(str(value)))
        self.total_label.setText(f"Total: {brl(sum((item.total for item in self.items), Decimal('0')))}"); self.table.resizeColumnsToContents()
    def data(self) -> PurchaseInput | None:
        supplier = None; supplier_name = self.supplier.currentText().strip()
        for index in range(self.supplier.count()):
            if self.supplier.itemText(index).casefold() == supplier_name.casefold(): supplier = self.supplier.itemData(index); supplier_name = self.supplier.itemText(index); break
        if not supplier: QMessageBox.warning(self, "Compra", "Selecione um fornecedor cadastrado na lista."); return None
        try:
            terms = [int(value.strip()) for value in self.terms.text().split("/") if value.strip()] if self.payment.currentData() == PurchasePaymentMethod.CREDIT else []
            return PurchaseInput(supplier_id=str(supplier[0]), supplier_name=supplier_name, supplier_whatsapp=supplier[1], items=self.items, payment_method=self.payment.currentData(), due_date=self.due.date().toPython() if self.payment.currentData() == PurchasePaymentMethod.BOLETO else None, installment_days=terms, notes=self.notes.toPlainText() or None)
        except (ValidationError, ValueError) as exc: QMessageBox.warning(self, "Compra inválida", exc.errors()[0]["msg"] if isinstance(exc, ValidationError) else str(exc)); return None
    def accept(self) -> None:
        if self.data(): super().accept()
