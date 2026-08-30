"""Painel de estoque, lotes, validade e inventário."""

from datetime import date, timedelta

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QInputDialog, QLabel, QMessageBox, QPushButton, QSpinBox, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from dialogs.stock_dialogs import InventoryDialog, StockMovementDialog
from dialogs.invoice_entry_dialog import InvoiceExpiryDialog
from models.auth import AuthenticatedSession, Permission
from services.catalog import CatalogService
from services.stock import StockService
from services.purchases import PurchaseService


class StockView(QWidget):
    def __init__(self, session: AuthenticatedSession, stock_service: StockService, catalog_service: CatalogService, purchase_service: PurchaseService, parent=None) -> None:
        super().__init__(parent); self.session = session; self.stock_service = stock_service; self.catalog_service = catalog_service; self.purchase_service = purchase_service
        root = QVBoxLayout(self); title = QLabel("Estoque"); title.setObjectName("pageTitle"); root.addWidget(title)
        actions = QHBoxLayout(); invoice_entry = QPushButton("Entrada de NF-e"); invoice_entry.clicked.connect(self._invoice_entry); movement = QPushButton("Nova movimentação"); movement.clicked.connect(self._movement); inventory = QPushButton("Realizar inventário"); inventory.clicked.connect(self._inventory); refresh = QPushButton("Atualizar"); refresh.clicked.connect(self.refresh)
        if Permission.STOCK_ADJUST not in session.permissions: invoice_entry.hide(); movement.hide(); inventory.hide()
        actions.addWidget(invoice_entry); actions.addWidget(movement); actions.addWidget(inventory); actions.addWidget(refresh); actions.addStretch(); actions.addWidget(QLabel("Alerta de validade (dias)")); self.expiry_days = QSpinBox(); self.expiry_days.setRange(0, 3650); self.expiry_days.setValue(30); self.expiry_days.valueChanged.connect(self.refresh_lots); actions.addWidget(self.expiry_days); root.addLayout(actions)
        tabs = QTabWidget(); root.addWidget(tabs)
        self.stock_table = QTableWidget(0, 6); self.stock_table.setHorizontalHeaderLabels(["Produto", "Saldo em unidades", "Saldo convertido", "Estoque mínimo", "Situação", "Localização"]); tabs.addTab(self.stock_table, "Saldos")
        self.movement_table = QTableWidget(0, 10); self.movement_table.setHorizontalHeaderLabels(["Data", "Produto", "Movimentação", "Embalagem", "Qtd. informada", "Unidades", "Saldo anterior", "Saldo final", "Usuário", "Motivo"]); tabs.addTab(self.movement_table, "Movimentações")
        self.lot_table = QTableWidget(0, 5); self.lot_table.setHorizontalHeaderLabels(["Produto", "Lote", "Quantidade", "Validade", "Situação"]); tabs.addTab(self.lot_table, "Lotes e validade")
        for table in (self.stock_table, self.movement_table, self.lot_table): table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); table.setAlternatingRowColors(True)
        self.refresh()

    def refresh(self) -> None: self.refresh_stock(); self.refresh_movements(); self.refresh_lots()
    def _products(self):
        try: return self.catalog_service.active_products(self.session)
        except PermissionError as exc: QMessageBox.warning(self, "Estoque", str(exc)); return []
    def refresh_stock(self) -> None:
        products = self._products(); self.stock_table.setRowCount(len(products))
        for row, product in enumerate(products):
            low = product.current_stock_units <= product.minimum_stock; values = (product.name, product.current_stock_units, product.stock_display, product.minimum_stock, "ESTOQUE BAIXO" if low else "Normal", product.storage_location or "—")
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value));
                if low: item.setForeground(Qt.GlobalColor.red)
                self.stock_table.setItem(row, column, item)
        self.stock_table.resizeColumnsToContents()
    def refresh_movements(self) -> None:
        try: movements, _ = self.stock_service.list_movements(self.session, page=1, page_size=100)
        except PermissionError as exc: QMessageBox.warning(self, "Estoque", str(exc)); return
        self.movement_table.setRowCount(len(movements))
        for row, movement in enumerate(movements):
            values = (movement.occurred_at.astimezone().strftime("%d/%m/%Y %H:%M"), movement.product_name, movement.movement_type.value.replace("_", " ").title(), movement.package_type.value.title(), movement.informed_quantity, movement.converted_units, movement.balance_before, movement.balance_after, movement.username, movement.reason)
            for column, value in enumerate(values): self.movement_table.setItem(row, column, QTableWidgetItem(str(value)))
        self.movement_table.resizeColumnsToContents()
    def refresh_lots(self) -> None:
        try: lots = self.stock_service.list_lots(self.session)
        except (ValueError, PermissionError) as exc: QMessageBox.warning(self, "Lotes", str(exc)); return
        today = date.today(); alert_limit = today + timedelta(days=self.expiry_days.value()); self.lot_table.setRowCount(len(lots))
        for row, lot in enumerate(lots):
            if lot.expiration_date is None: situation = "Sem validade"
            elif lot.expiration_date < today: situation = "VENCIDO"
            elif lot.expiration_date <= alert_limit: situation = "Próximo do vencimento"
            else: situation = "Dentro da validade"
            for column, value in enumerate((lot.product_name, lot.code, lot.quantity_units, lot.expiration_date.strftime("%d/%m/%Y") if lot.expiration_date else "—", situation)): self.lot_table.setItem(row, column, QTableWidgetItem(str(value)))
        self.lot_table.resizeColumnsToContents()
    def _movement(self) -> None:
        dialog = StockMovementDialog(self._products(), self)
        if dialog.exec() != dialog.DialogCode.Accepted: return
        try:
            data = dialog.data()
            if data: self.stock_service.move(self.session, data); self.refresh()
        except (ValueError, RuntimeError, PermissionError) as exc: QMessageBox.warning(self, "Movimentação não realizada", str(exc))
    def _invoice_entry(self) -> None:
        number, accepted = QInputDialog.getText(self, "Entrada de NF-e", "Número do pedido:")
        if not accepted or not number.strip(): return
        try: purchase = self.purchase_service.invoice_entry_info(self.session, number)
        except (ValueError, RuntimeError, PermissionError) as exc: QMessageBox.warning(self, "Entrada de NF-e", str(exc)); return
        expiry_dialog = InvoiceExpiryDialog(purchase, self)
        if expiry_dialog.exec() != expiry_dialog.DialogCode.Accepted: return
        expiration_dates = expiry_dialog.expiration_dates()
        item_lines = "\n".join(f"• {item.product_name}: {item.quantity} {('fardo(s)' if item.package_type.value == 'fardo' else 'unidade(s)')} = {item.converted_units} un." for item in purchase.items)
        validity_lines = "\n".join(f"• {item.product_name}: {expiration_dates[item.product_id].strftime('%d/%m/%Y')}" for item in purchase.items)
        details = f"Pedido: {purchase.number}\nFornecedor: {purchase.supplier_name}\nNotas vinculadas: {', '.join(purchase.invoice_numbers)}\n\nItens:\n{item_lines}\n\nValidades:\n{validity_lines}\n\nConfirmar a entrada e atualizar o estoque?"
        if QMessageBox.question(self, "Confirmar entrada de NF-e", details) != QMessageBox.StandardButton.Yes: return
        try:
            completed = self.purchase_service.post_invoice_entry(self.session, purchase.id or "", expiration_dates); self.refresh(); QMessageBox.information(self, "Entrada concluída", f"Entrada do pedido {completed.number} concluída.\nEstoque e validades atualizados com todas as notas vinculadas.")
        except (ValueError, RuntimeError, PermissionError) as exc: QMessageBox.warning(self, "Entrada não realizada", str(exc)); self.refresh()
    def _inventory(self) -> None:
        dialog = InventoryDialog(self._products(), self)
        if dialog.exec() != dialog.DialogCode.Accepted: return
        try:
            data = dialog.data()
            if data: self.stock_service.inventory(self.session, data); self.refresh()
        except (ValueError, RuntimeError, PermissionError) as exc: QMessageBox.warning(self, "Inventário não realizado", str(exc))
