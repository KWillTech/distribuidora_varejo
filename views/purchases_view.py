"""Tela de pedidos de compra, recebimento e cancelamento."""

import re
from pathlib import Path
from urllib.parse import quote

from PySide6.QtCore import Qt, QUrl, QStandardPaths
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QComboBox, QFileDialog, QHBoxLayout, QInputDialog, QLabel, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from dialogs.purchase_dialog import PurchaseDialog
from models.auth import AuthenticatedSession, Permission
from models.purchase import Purchase, PurchaseStatus
from services.catalog import CatalogService
from services.purchases import PurchaseService
from services.suppliers import SupplierService
from views.dashboard_view import brl


class PurchasesView(QWidget):
    def __init__(self, session: AuthenticatedSession, service: PurchaseService, suppliers: SupplierService, catalog: CatalogService, parent=None) -> None:
        super().__init__(parent); self.session = session; self.service = service; self.suppliers = suppliers; self.catalog = catalog
        root = QVBoxLayout(self); title = QLabel("Compras"); title.setObjectName("pageTitle"); root.addWidget(title); actions = QHBoxLayout(); self.status = QComboBox(); self.status.addItem("Todas", None)
        for value, label in ((PurchaseStatus.SENT, "Pedidos enviados"), (PurchaseStatus.RECEIPT_CONFIRMED, "Recebimento confirmado"), (PurchaseStatus.PENDING, "Aguardando envio"), (PurchaseStatus.RECEIVED, "Concluídos"), (PurchaseStatus.CANCELLED, "Canceladas"), (PurchaseStatus.FAILED, "Falha no recebimento")): self.status.addItem(label, value.value)
        self.status.currentIndexChanged.connect(self.refresh); new = QPushButton("Nova compra"); new.clicked.connect(self._new); show = QPushButton("Exibir pedido"); show.clicked.connect(self._show_order); show_invoices = QPushButton("Exibir NF-e"); show_invoices.clicked.connect(self._show_invoices); receive = QPushButton("Confirmar recebimento"); receive.clicked.connect(self._receive); cancel = QPushButton("Cancelar compra"); cancel.clicked.connect(self._cancel); refresh = QPushButton("Atualizar"); refresh.clicked.connect(self.refresh)
        if Permission.PURCHASES_CREATE not in session.permissions: new.hide(); receive.hide()
        if Permission.PURCHASES_CANCEL not in session.permissions: cancel.hide()
        actions.addWidget(self.status); actions.addWidget(new); actions.addWidget(show); actions.addWidget(show_invoices); actions.addWidget(receive); actions.addWidget(cancel); actions.addWidget(refresh); actions.addStretch(); root.addLayout(actions)
        self.table = QTableWidget(0, 8); self.table.setHorizontalHeaderLabels(["Número", "Data", "Fornecedor", "NF-e", "Itens", "Pagamento", "Total", "Status"]); self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); self.table.setAlternatingRowColors(True); root.addWidget(self.table); self.refresh()
    def refresh(self) -> None:
        try: purchases, _ = self.service.list_page(self.session, status=self.status.currentData(), page=1, page_size=100)
        except PermissionError as exc: QMessageBox.warning(self, "Compras", str(exc)); return
        self.table.setRowCount(len(purchases))
        for row, purchase in enumerate(purchases):
            status_label = "Concluído" if purchase.status == PurchaseStatus.RECEIVED else purchase.status.value.replace("_", " ").title()
            values = (purchase.number, purchase.created_at.astimezone().strftime("%d/%m/%Y %H:%M"), purchase.supplier_name, purchase.invoice_number or "—", len(purchase.items), purchase.payment_method.value.replace("_", " ").title(), brl(purchase.total), status_label)
            for column, value in enumerate(values): item = QTableWidgetItem(str(value)); item.setData(Qt.ItemDataRole.UserRole, purchase); self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()
    def _selected(self) -> Purchase | None:
        row = self.table.currentRow()
        if row < 0: QMessageBox.information(self, "Seleção", "Selecione uma compra."); return None
        return self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
    def _show_order(self) -> None:
        purchase = self._selected()
        if not purchase: return
        if purchase.pdf_path and Path(purchase.pdf_path).exists(): QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(purchase.pdf_path).resolve())))
        else:
            status_label = "Concluído" if purchase.status == PurchaseStatus.RECEIVED else purchase.status.value.replace("_", " ").title()
            QMessageBox.information(self, "Pedido", f"Pedido: {purchase.number}\nFornecedor: {purchase.supplier_name}\nItens: {len(purchase.items)}\nTotal: {brl(purchase.total)}\nStatus: {status_label}")
    def _show_invoices(self) -> None:
        purchase = self._selected()
        if not purchase: return
        if not purchase.invoice_numbers: QMessageBox.information(self, "NF-e", f"O pedido {purchase.number} ainda não possui NF-e vinculada."); return
        notes = "\n".join(f"{index}. {number}" for index, number in enumerate(purchase.invoice_numbers, 1))
        QMessageBox.information(self, "NF-e vinculadas", f"Pedido: {purchase.number}\nFornecedor: {purchase.supplier_name}\n\nNotas fiscais:\n{notes}")
    def _new(self) -> None:
        try: supplier_options = self.suppliers.active_options(self.session); products = self.catalog.active_products(self.session)
        except PermissionError as exc: QMessageBox.warning(self, "Compra", str(exc)); return
        if not supplier_options or not products: QMessageBox.warning(self, "Compra", "Cadastre ao menos um fornecedor e um produto ativos."); return
        dialog = PurchaseDialog(supplier_options, products, self)
        if dialog.exec() != dialog.DialogCode.Accepted: return
        try:
            data = dialog.data()
            if data:
                initial = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
                folder = QFileDialog.getExistingDirectory(self, "Escolha onde salvar o PDF do pedido", initial)
                if not folder: return
                purchase = self.service.create_order(self.session, data, Path(folder)); self._open_whatsapp(purchase); self.refresh()
        except (ValueError, RuntimeError, PermissionError, OSError) as exc: QMessageBox.warning(self, "Pedido não enviado", str(exc)); self.refresh()

    def _open_whatsapp(self, purchase: Purchase) -> None:
        pdf_path = Path(purchase.pdf_path or "").resolve(); phone = re.sub(r"\D", "", purchase.supplier_whatsapp or "")
        if phone and len(phone) in (10, 11): phone = "55" + phone
        message = quote("Olá! Segue anexo a lista do pedido de compras")
        opened = bool(phone) and QDesktopServices.openUrl(QUrl(f"https://wa.me/{phone}?text={message}"))
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(pdf_path.parent)))
        detail = "O WhatsApp foi aberto com a mensagem pronta." if opened else "O fornecedor não possui um WhatsApp válido cadastrado."
        QMessageBox.information(self, "Pedido gerado", f"Pedido {purchase.number} gerado com sucesso.\n\n{detail}\nAnexe o arquivo ao envio:\n{pdf_path}")

    def _receive(self) -> None:
        purchase = self._selected()
        if not purchase: return
        if purchase.status not in (PurchaseStatus.SENT, PurchaseStatus.PENDING): QMessageBox.information(self, "Recebimento", "Selecione um pedido enviado."); return
        notes_text, accepted = QInputDialog.getMultiLineText(self, "Notas fiscais do recebimento", "Informe o número de cada nota fiscal.\nPara mais de uma nota, use uma linha, vírgula ou ponto e vírgula:")
        if not accepted: return
        invoice_numbers = [value.strip() for value in re.split(r"[\n,;]+", notes_text) if value.strip()]
        if not invoice_numbers: QMessageBox.warning(self, "Notas fiscais", "Informe pelo menos um número de nota fiscal."); return
        answer = QMessageBox.question(self, "Confirmar recebimento", f"Confirmar o recebimento do pedido {purchase.number} e vincular {len(invoice_numbers)} nota(s)?\n\nO estoque não será atualizado nesta etapa.")
        if answer != QMessageBox.StandardButton.Yes: return
        try: received = self.service.confirm_receipt(self.session, purchase.id or "", invoice_numbers); QMessageBox.information(self, "Recebimento confirmado", f"Recebimento do pedido {received.number} confirmado sem alterar o estoque.\nNotas: {', '.join(received.invoice_numbers)}\n\nFaça a entrada pela aba Estoque > Entrada de NF-e."); self.refresh()
        except (ValueError, RuntimeError, PermissionError) as exc: QMessageBox.warning(self, "Recebimento não realizado", str(exc)); self.refresh()
    def _cancel(self) -> None:
        purchase = self._selected()
        if not purchase: return
        reason, accepted = QInputDialog.getText(self, "Cancelar compra", "Motivo do cancelamento:")
        if not accepted: return
        try: self.service.cancel(self.session, purchase.id or "", reason); self.refresh()
        except (ValueError, RuntimeError, PermissionError) as exc: QMessageBox.warning(self, "Cancelamento não realizado", str(exc))
