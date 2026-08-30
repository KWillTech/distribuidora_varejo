"""Tela de abertura, movimentação e fechamento de caixa."""
from decimal import Decimal
from PySide6.QtWidgets import QHBoxLayout,QInputDialog,QLabel,QMessageBox,QPushButton,QTableWidget,QTableWidgetItem,QVBoxLayout,QWidget
from dialogs.catalog_dialogs import parse_money
from models.auth import AuthenticatedSession,Permission
from models.cash import CashCloseInput
from services.cash import CashService
from views.dashboard_view import brl
class CashView(QWidget):
    def __init__(self,session:AuthenticatedSession,service:CashService,parent=None):
        super().__init__(parent); self.session=session; self.service=service; root=QVBoxLayout(self); title=QLabel("Caixa"); title.setObjectName("pageTitle"); root.addWidget(title); self.status=QLabel(); self.status.setObjectName("metricValue"); root.addWidget(self.status); self.table=QTableWidget(0,7); self.table.setHorizontalHeaderLabels(["Abertura","Usuário","Inicial","Esperado","Contado","Diferença","Status"]); root.addWidget(self.table); self.refresh()
    def _money(self,title,label, positive=True):
        text,ok=QInputDialog.getText(self,title,label)
        if not ok:return None
        try:return parse_money(text, positive)
        except ValueError as exc: QMessageBox.warning(self,title,str(exc)); return None
    def _open(self):
        amount=self._money("Abrir caixa","Valor inicial:",False)
        if amount is None:return
        try:self.service.open(self.session,amount); self.refresh()
        except Exception as exc: QMessageBox.warning(self,"Caixa",str(exc))
    def _supply(self): self._movement("Suprimento",self.service.supply)
    def _withdraw(self): self._movement("Sangria",self.service.withdraw)
    def _movement(self,title,operation):
        amount=self._money(title,"Valor:")
        if amount is None:return
        reason,ok=QInputDialog.getText(self,title,"Motivo:")
        if not ok or len(reason.strip())<3: QMessageBox.warning(self,title,"Informe o motivo."); return
        try:operation(self.session,amount,reason); self.refresh()
        except Exception as exc: QMessageBox.warning(self,title,str(exc))
    def _close(self):
        counted=self._money("Fechar caixa","Valor contado:",False)
        if counted is None:return
        current=self.service.current(self.session)
        if not current: QMessageBox.warning(self,"Fechar caixa","Não há caixa aberto."); return
        justification=None
        if counted!=current.expected_amount:
            justification,ok=QInputDialog.getText(self,"Diferença de caixa",f"Esperado: {brl(current.expected_amount)}\nDiferença: {brl(counted-current.expected_amount)}\nJustificativa:")
            if not ok:return
        try:self.service.close(self.session,CashCloseInput(counted_amount=counted,justification=justification)); self.refresh()
        except Exception as exc: QMessageBox.warning(self,"Fechar caixa",str(exc))
    def refresh(self):
        try: current=self.service.current(self.session); rows=self.service.history(self.session)
        except Exception as exc: QMessageBox.warning(self,"Caixa",str(exc)); return
        self.status.setText(f"Caixa aberto — saldo esperado: {brl(current.expected_amount)}" if current else "Nenhum caixa aberto")
        self.table.setRowCount(len(rows))
        for row,cash in enumerate(rows):
            values=(cash.opened_at.astimezone().strftime("%d/%m/%Y %H:%M"),cash.username,brl(cash.opening_amount),brl(cash.expected_amount),brl(cash.counted_amount) if cash.counted_amount is not None else "—",brl(cash.difference) if cash.difference is not None else "—",cash.status.value.title())
            for column,value in enumerate(values):self.table.setItem(row,column,QTableWidgetItem(str(value)))
        self.table.resizeColumnsToContents()
