"""Listagem, manutenção e histórico de fornecedores."""

from decimal import Decimal
from math import ceil

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from dialogs.supplier_dialog import SupplierDialog
from models.auth import AuthenticatedSession, Permission
from models.supplier import Supplier
from services.suppliers import SupplierService
from views.dashboard_view import brl


def format_document(value: str) -> str:
    if len(value) == 11: return f"{value[:3]}.{value[3:6]}.{value[6:9]}-{value[9:]}"
    return f"{value[:2]}.{value[2:5]}.{value[5:8]}/{value[8:12]}-{value[12:]}"


class SuppliersView(QWidget):
    def __init__(self, session: AuthenticatedSession, service: SupplierService, parent=None) -> None:
        super().__init__(parent); self.session = session; self.service = service; self.page = 1; self.total_pages = 1
        root = QVBoxLayout(self); title = QLabel("Fornecedores"); title.setObjectName("pageTitle"); root.addWidget(title)
        filters = QHBoxLayout(); self.search = QLineEdit(); self.search.setPlaceholderText("Pesquisar por razão social, nome fantasia, CPF ou CNPJ…"); self.search.setClearButtonEnabled(True)
        self.timer = QTimer(self); self.timer.setSingleShot(True); self.timer.setInterval(350); self.search.textChanged.connect(self.timer.start); self.timer.timeout.connect(self._first)
        self.status = QComboBox(); self.status.addItem("Ativos", True); self.status.addItem("Inativos", False); self.status.addItem("Todos", None); self.status.currentIndexChanged.connect(self._first)
        self.size = QComboBox(); self.size.addItems(["10", "20", "50", "100"]); self.size.setCurrentText("20"); self.size.currentIndexChanged.connect(self._first)
        new = QPushButton("Novo fornecedor"); new.clicked.connect(self._create)
        if Permission.SUPPLIERS_CREATE not in session.permissions: new.hide()
        filters.addWidget(self.search, 1); filters.addWidget(self.status); filters.addWidget(QLabel("Por página")); filters.addWidget(self.size); filters.addWidget(new); root.addLayout(filters)
        self.table = QTableWidget(0, 7); self.table.setHorizontalHeaderLabels(["Razão social", "Nome fantasia", "CPF/CNPJ", "Telefone", "Última compra", "Total comprado", "Status"]); self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); self.table.setAlternatingRowColors(True); self.table.doubleClicked.connect(self._edit); root.addWidget(self.table)
        actions = QHBoxLayout(); edit = QPushButton("Editar"); edit.clicked.connect(self._edit); toggle = QPushButton("Ativar/Inativar"); toggle.clicked.connect(self._toggle); details = QPushButton("Compras e últimos custos"); details.clicked.connect(self._details)
        if Permission.SUPPLIERS_EDIT not in session.permissions: edit.hide()
        if Permission.SUPPLIERS_DEACTIVATE not in session.permissions: toggle.hide()
        actions.addWidget(edit); actions.addWidget(toggle); actions.addWidget(details); actions.addStretch(); self.previous = QPushButton("Anterior"); self.previous.clicked.connect(self._previous); self.page_label = QLabel(); self.next = QPushButton("Próxima"); self.next.clicked.connect(self._next); actions.addWidget(self.previous); actions.addWidget(self.page_label); actions.addWidget(self.next); root.addLayout(actions); self.refresh()

    def _first(self) -> None: self.page = 1; self.refresh()
    def refresh(self) -> None:
        try: result = self.service.list_page(self.session, search=self.search.text(), active=self.status.currentData(), page=self.page, page_size=int(self.size.currentText()))
        except (ValueError, PermissionError) as exc: QMessageBox.warning(self, "Fornecedores", str(exc)); return
        self.total_pages = max(1, ceil(result.total / result.page_size)); self.table.setRowCount(len(result.items))
        for row, supplier in enumerate(result.items):
            values = (supplier.legal_name, supplier.trade_name or "—", format_document(supplier.document), supplier.phone or "—", supplier.last_purchase_at.strftime("%d/%m/%Y") if supplier.last_purchase_at else "—", brl(supplier.total_purchased), "Ativo" if supplier.active else "Inativo")
            for column, value in enumerate(values): item = QTableWidgetItem(str(value)); item.setData(Qt.ItemDataRole.UserRole, supplier); self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents(); self.page_label.setText(f"Página {self.page} de {self.total_pages} • {result.total} fornecedor(es)"); self.previous.setEnabled(self.page > 1); self.next.setEnabled(self.page < self.total_pages)

    def _selected(self) -> Supplier | None:
        row = self.table.currentRow()
        if row < 0: QMessageBox.information(self, "Seleção", "Selecione um fornecedor."); return None
        return self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
    def _create(self) -> None:
        dialog = SupplierDialog(parent=self)
        if dialog.exec() != dialog.DialogCode.Accepted: return
        try:
            data = dialog.data()
            if data: self.service.create(self.session, data); self._first()
        except (ValueError, RuntimeError, PermissionError) as exc: QMessageBox.warning(self, "Cadastro não realizado", str(exc))
    def _edit(self) -> None:
        supplier = self._selected()
        if not supplier: return
        try: supplier = self.service.get(self.session, supplier.id or "")
        except (ValueError, PermissionError) as exc: QMessageBox.warning(self, "Fornecedor", str(exc)); return
        dialog = SupplierDialog(supplier, self)
        if dialog.exec() != dialog.DialogCode.Accepted: return
        try:
            data = dialog.data()
            if data: self.service.update(self.session, supplier.id or "", data); self.refresh()
        except (ValueError, RuntimeError, PermissionError) as exc: QMessageBox.warning(self, "Alteração não realizada", str(exc))
    def _toggle(self) -> None:
        supplier = self._selected()
        if not supplier: return
        reason, accepted = QInputDialog.getText(self, "Motivo", "Informe o motivo:")
        if not accepted: return
        try: self.service.set_active(self.session, supplier.id or "", not supplier.active, reason); self.refresh()
        except (ValueError, PermissionError) as exc: QMessageBox.warning(self, "Operação não realizada", str(exc))
    def _details(self) -> None:
        supplier = self._selected()
        if not supplier: return
        try: purchases, costs = self.service.purchase_details(self.session, supplier.id or "")
        except (ValueError, PermissionError) as exc: QMessageBox.warning(self, "Histórico", str(exc)); return
        lines = [f"Compras registradas: {len(purchases)}", "", "Histórico de compras:"]
        lines.extend(f"• Nota {item.get('numero_nota') or '—'} — {item.get('data_hora').strftime('%d/%m/%Y') if item.get('data_hora') else '—'} — {brl(Decimal(str(item.get('total', 0))))}" for item in purchases)
        if not purchases: lines.append("Nenhuma compra registrada.")
        lines.extend(("", "Últimos custos:"))
        lines.extend(f"• {item.get('produto') or 'Produto'} — {brl(Decimal(str(item.get('custo_unitario', 0))))}" for item in costs)
        if not costs: lines.append("Nenhum custo registrado.")
        QMessageBox.information(self, f"Compras — {supplier.legal_name}", "\n".join(lines))
    def _previous(self) -> None: self.page -= 1; self.refresh()
    def _next(self) -> None: self.page += 1; self.refresh()
