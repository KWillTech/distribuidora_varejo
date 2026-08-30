"""Tela paginada de clientes, sem acesso direto ao banco."""

from __future__ import annotations

from decimal import Decimal
from math import ceil

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QInputDialog, QLabel, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from dialogs.customer_dialog import CustomerDialog
from models.auth import AuthenticatedSession, Permission
from models.customer import Customer
from services.customers import CustomerService
from views.dashboard_view import brl


def format_cpf(value: str | None) -> str:
    if not value: return "—"
    return f"{value[:3]}.{value[3:6]}.{value[6:9]}-{value[9:]}"


def format_phone(value: str | None) -> str:
    if not value: return "—"
    if len(value) == 11: return f"({value[:2]}) {value[2:7]}-{value[7:]}"
    return f"({value[:2]}) {value[2:6]}-{value[6:]}"


class CustomersView(QWidget):
    def __init__(self, session: AuthenticatedSession, service: CustomerService, parent=None) -> None:
        super().__init__(parent)
        self.session = session; self.service = service; self.page = 1; self.total_pages = 1
        root = QVBoxLayout(self)
        title = QLabel("Clientes"); title.setObjectName("pageTitle"); root.addWidget(title)
        filters = QHBoxLayout()
        from PySide6.QtWidgets import QLineEdit
        self.search = QLineEdit(); self.search.setPlaceholderText("Pesquisar por nome, CPF ou celular…"); self.search.setClearButtonEnabled(True)
        self.search_timer = QTimer(self); self.search_timer.setSingleShot(True); self.search_timer.setInterval(350); self.search.textChanged.connect(lambda: self.search_timer.start()); self.search_timer.timeout.connect(self._first_page)
        self.status = QComboBox(); self.status.addItem("Ativos", True); self.status.addItem("Inativos", False); self.status.addItem("Todos", None); self.status.currentIndexChanged.connect(self._first_page)
        self.page_size = QComboBox(); self.page_size.addItems(["10", "20", "50", "100"]); self.page_size.setCurrentText("20"); self.page_size.currentIndexChanged.connect(self._first_page)
        self.new_button = QPushButton("Novo cliente"); self.new_button.clicked.connect(self._create)
        if Permission.CUSTOMERS_CREATE not in session.permissions: self.new_button.hide()
        filters.addWidget(self.search, 1); filters.addWidget(self.status); filters.addWidget(QLabel("Por página")); filters.addWidget(self.page_size); filters.addWidget(self.new_button); root.addLayout(filters)
        self.table = QTableWidget(0, 7); self.table.setHorizontalHeaderLabels(["Nome", "CPF", "Telefone", "Cidade", "Total gasto", "Última compra", "Status"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); self.table.setAlternatingRowColors(True); self.table.doubleClicked.connect(self._edit)
        root.addWidget(self.table)
        actions = QHBoxLayout()
        self.edit_button = QPushButton("Editar"); self.edit_button.clicked.connect(self._edit)
        if Permission.CUSTOMERS_EDIT not in session.permissions: self.edit_button.hide()
        self.active_button = QPushButton("Ativar/Inativar"); self.active_button.clicked.connect(self._toggle_active)
        if Permission.CUSTOMERS_DEACTIVATE not in session.permissions: self.active_button.hide()
        self.history_button = QPushButton("Histórico de compras"); self.history_button.clicked.connect(self._history)
        actions.addWidget(self.edit_button); actions.addWidget(self.active_button); actions.addWidget(self.history_button); actions.addStretch()
        self.previous = QPushButton("Anterior"); self.previous.clicked.connect(self._previous); self.page_label = QLabel(); self.next = QPushButton("Próxima"); self.next.clicked.connect(self._next)
        actions.addWidget(self.previous); actions.addWidget(self.page_label); actions.addWidget(self.next); root.addLayout(actions)
        self.refresh()

    def _first_page(self) -> None: self.page = 1; self.refresh()

    def refresh(self) -> None:
        try:
            result = self.service.list_page(self.session, search=self.search.text(), active=self.status.currentData(), page=self.page, page_size=int(self.page_size.currentText()))
        except (ValueError, PermissionError) as exc:
            QMessageBox.warning(self, "Clientes", str(exc)); return
        self.total_pages = max(1, ceil(result.total / result.page_size)); self.page = min(self.page, self.total_pages)
        self.table.setRowCount(len(result.items))
        for row, customer in enumerate(result.items):
            values = (customer.full_name or "Não informado", format_cpf(customer.cpf), format_phone(customer.phone), customer.main_address.city if customer.main_address else "—", brl(customer.total_spent), customer.last_purchase_at.strftime("%d/%m/%Y") if customer.last_purchase_at else "—", "Ativo" if customer.active else "Inativo")
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value)); item.setData(Qt.ItemDataRole.UserRole, customer); self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents(); self.page_label.setText(f"Página {self.page} de {self.total_pages} • {result.total} cliente(s)"); self.previous.setEnabled(self.page > 1); self.next.setEnabled(self.page < self.total_pages)

    def _selected(self) -> Customer | None:
        row = self.table.currentRow()
        if row < 0: QMessageBox.information(self, "Seleção", "Selecione um cliente."); return None
        return self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)

    def _create(self) -> None:
        dialog = CustomerDialog(parent=self,session=self.session)
        if dialog.exec() != dialog.DialogCode.Accepted: return
        data = dialog.data()
        try:
            if data: self.service.create(self.session, data); self._first_page()
        except (ValueError, RuntimeError, PermissionError) as exc: QMessageBox.warning(self, "Cadastro não realizado", str(exc))

    def _edit(self) -> None:
        customer = self._selected()
        if not customer: return
        try: customer = self.service.get(self.session, customer.id or "")
        except (ValueError, PermissionError) as exc: QMessageBox.warning(self, "Cliente", str(exc)); return
        dialog = CustomerDialog(customer, self,session=self.session)
        if dialog.exec() != dialog.DialogCode.Accepted: return
        data = dialog.data()
        try:
            if data: self.service.update(self.session, customer.id or "", data); self.refresh()
        except (ValueError, RuntimeError, PermissionError) as exc: QMessageBox.warning(self, "Alteração não realizada", str(exc))

    def _toggle_active(self) -> None:
        customer = self._selected()
        if not customer: return
        reason, accepted = QInputDialog.getText(self, "Motivo", "Informe o motivo:")
        if not accepted: return
        try: self.service.set_active(self.session, customer.id or "", not customer.active, reason); self.refresh()
        except (ValueError, PermissionError) as exc: QMessageBox.warning(self, "Operação não realizada", str(exc))

    def _history(self) -> None:
        customer = self._selected()
        if not customer: return
        try:
            full = self.service.get(self.session, customer.id or ""); sales = self.service.purchase_history(self.session, customer.id or "")
        except (ValueError, PermissionError) as exc: QMessageBox.warning(self, "Histórico", str(exc)); return
        lines = [f"Total gasto: {brl(full.total_spent)}", f"Ticket médio: {brl(full.average_ticket)}", f"Última compra: {full.last_purchase_at.strftime('%d/%m/%Y %H:%M') if full.last_purchase_at else '—'}", "", "Compras:"]
        lines.extend(f"• {sale.get('numero', '—')} — {sale.get('data_hora').strftime('%d/%m/%Y') if sale.get('data_hora') else '—'} — {brl(Decimal(str(sale.get('total', 0))))}" for sale in sales)
        if not sales: lines.append("Nenhuma compra registrada.")
        QMessageBox.information(self, f"Histórico — {customer.full_name or 'Cliente sem nome'}", "\n".join(lines))

    def _previous(self) -> None: self.page -= 1; self.refresh()
    def _next(self) -> None: self.page += 1; self.refresh()
