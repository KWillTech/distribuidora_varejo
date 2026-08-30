"""Pagamento simples ou misto no PDV."""
from decimal import Decimal
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QCheckBox,QComboBox,QDateEdit,QDialog,QDialogButtonBox,QFormLayout,QHBoxLayout,QLabel,QLineEdit,QMessageBox,QPushButton,QTableWidget,QTableWidgetItem,QVBoxLayout
from dialogs.catalog_dialogs import parse_money
from models.sale import PaymentMethod,SalePayment
from views.dashboard_view import brl

class PaymentDialog(QDialog):
    def __init__(self,total:Decimal,parent=None,customer=None,session=None,credit=None):
        super().__init__(parent); self.total=total; self.customer=customer; self.session=session; self.credit=credit; self.payments=[]; self.setWindowTitle("Pagamento"); root=QVBoxLayout(self); root.addWidget(QLabel(f"Total: {brl(total)}")); self.credit_info=QLabel(); self.credit_info.setWordWrap(True); root.addWidget(self.credit_info); form=QFormLayout(); self.method=QComboBox()
        for value,label in ((PaymentMethod.CASH,"Dinheiro"),(PaymentMethod.PIX,"Pix"),(PaymentMethod.DEBIT,"Débito"),(PaymentMethod.CREDIT,"Crédito"),(PaymentMethod.INSTALLMENT_CREDIT,"Crédito parcelado"),(PaymentMethod.STORE_CREDIT,"Fiado")): self.method.addItem(label,value)
        self.amount=QLineEdit(); self.amount.setPlaceholderText("0,00"); self.due=QDateEdit(QDate.currentDate().addDays(customer.credit.due_days if customer else 30)); self.due.setCalendarPopup(True); self.due.setDisplayFormat("dd/MM/yyyy"); self.allow_overdue=QCheckBox("Autorizo cliente com conta vencida"); self.allow_limit=QCheckBox("Autorizo ultrapassar limite"); self.justification=QLineEdit(); self.justification.setPlaceholderText("Justificativa da autorização"); form.addRow("Forma",self.method); form.addRow("Valor",self.amount); form.addRow("Vencimento do fiado",self.due); form.addRow("",self.allow_overdue); form.addRow("",self.allow_limit); form.addRow("Justificativa",self.justification); root.addLayout(form); self.method.currentIndexChanged.connect(self._method_changed); self._method_changed()
        add=QPushButton("Adicionar pagamento"); add.clicked.connect(self._add); root.addWidget(add); self.table=QTableWidget(0,2); self.table.setHorizontalHeaderLabels(["Forma","Valor"]); root.addWidget(self.table); self.summary=QLabel(); root.addWidget(self.summary); buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel); buttons.button(QDialogButtonBox.StandardButton.Save).setText("Finalizar venda"); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons); self._refresh()
    def _method_changed(self):
        credit=self.method.currentData()==PaymentMethod.STORE_CREDIT
        for widget in (self.due,self.allow_overdue,self.allow_limit,self.justification):widget.setVisible(credit)
        if credit:
            if not self.customer:self.credit_info.setText("Selecione um cliente no PDV para utilizar fiado."); return
            profile=self.customer.credit; self.credit_info.setText(f"Cliente: {self.customer.full_name or 'Sem nome'} | Limite: {brl(profile.credit_limit)} | Saldo devedor: {brl(profile.debt_balance)} | Disponível: {brl(profile.available_limit)}")
        else:self.credit_info.clear()
    def _add(self):
        try:
            if self.method.currentData()==PaymentMethod.STORE_CREDIT and not self.customer:raise ValueError("Venda fiada exige cliente selecionado.")
            self.payments.append(SalePayment(method=self.method.currentData(),amount=parse_money(self.amount.text(),True))); self.amount.clear(); self._refresh()
        except Exception as exc: QMessageBox.warning(self,"Pagamento",str(exc))
    def _refresh(self):
        self.table.setRowCount(len(self.payments))
        for row,p in enumerate(self.payments): self.table.setItem(row,0,QTableWidgetItem(p.method.value.replace("_"," ").title())); self.table.setItem(row,1,QTableWidgetItem(brl(p.amount)))
        paid=sum((p.amount for p in self.payments),Decimal("0")); self.summary.setText(f"Pago: {brl(paid)}  |  Restante/Troco: {brl(abs(self.total-paid))}")
    def accept(self):
        if sum((p.amount for p in self.payments),Decimal("0"))<self.total: QMessageBox.warning(self,"Pagamento","O valor pago não cobre o total."); return
        credit=sum((p.amount for p in self.payments if p.method==PaymentMethod.STORE_CREDIT),Decimal("0"))
        if credit:
            paid=self.total-credit; profile=self.customer.credit
            text=f"Cliente: {self.customer.full_name}\nValor total: {brl(self.total)}\nPago agora: {brl(paid)}\nValor fiado: {brl(credit)}\nSaldo anterior: {brl(profile.debt_balance)}\nNovo saldo: {brl(profile.debt_balance+credit)}\nLimite disponível após: {brl(max(Decimal('0'),profile.available_limit-credit))}\nVencimento: {self.due.date().toString('dd/MM/yyyy')}\n\nConfirmar venda fiada?"
            if QMessageBox.question(self,"Confirmar venda fiada",text)!=QMessageBox.StandardButton.Yes:return
        super().accept()
