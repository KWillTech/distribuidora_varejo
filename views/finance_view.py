"""Visão de lançamentos e fluxo financeiro."""
from datetime import date
from decimal import Decimal
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QAbstractItemView,QCheckBox,QComboBox,QDateEdit,QDialog,QDialogButtonBox,QFormLayout,QHBoxLayout,QInputDialog,QLabel,QLineEdit,QMessageBox,QPlainTextEdit,QPushButton,QSpinBox,QTableWidget,QTableWidgetItem,QVBoxLayout,QWidget
from dialogs.catalog_dialogs import parse_money
from models.auth import Permission
from models.finance import FinancialInput,FinancialKind,FinancialStatus,PaymentInput
from views.dashboard_view import brl

KIND_LABELS={FinancialKind.PAYABLE:"Contas a pagar",FinancialKind.RECEIVABLE:"Contas a receber",FinancialKind.EXPENSE:"Despesas",FinancialKind.REVENUE:"Receitas"}
STATUS_LABELS={FinancialStatus.OPEN:"Aberta",FinancialStatus.PARTIAL:"Parcial",FinancialStatus.PAID:"Paga",FinancialStatus.CANCELLED:"Cancelada"}
class FinancialEntryDialog(QDialog):
    def __init__(self,parent=None,entry=None):
        super().__init__(parent); self.entry=entry; self.setWindowTitle("Editar despesa" if entry else "Novo lançamento financeiro"); self.setMinimumWidth(520); root=QVBoxLayout(self); form=QFormLayout(); self.kind=QComboBox()
        for kind in (FinancialKind.RECEIVABLE,FinancialKind.EXPENSE,FinancialKind.REVENUE):self.kind.addItem(KIND_LABELS[kind],kind)
        self.description=QLineEdit(); self.category=QLineEdit(); self.amount=QLineEdit(); self.amount.setPlaceholderText("0,00"); self.due=QDateEdit(QDate.currentDate()); self.due.setCalendarPopup(True); self.due.setDisplayFormat("dd/MM/yyyy"); self.notes=QPlainTextEdit(); self.notes.setMaximumHeight(90); self.recurring=QCheckBox("Habilitar recorrência mensal"); self.recurrence_count=QSpinBox(); self.recurrence_count.setRange(2,60); self.recurrence_count.setValue(12); self.recurrence_count.setEnabled(False); self.recurring.toggled.connect(self.recurrence_count.setEnabled)
        for label,widget in (("Tipo *",self.kind),("Descrição *",self.description),("Categoria *",self.category),("Valor *",self.amount),("Primeiro vencimento *",self.due),("Observações",self.notes),("Recorrência",self.recurring),("Quantidade de ocorrências",self.recurrence_count)):form.addRow(label,widget)
        if entry:
            self.kind.setCurrentIndex(self.kind.findData(FinancialKind.EXPENSE)); self.kind.setEnabled(False); self.description.setText(entry.description); self.category.setText(entry.category); self.amount.setText(str(entry.original_amount).replace(".",",")); self.due.setDate(QDate(entry.due_date.year,entry.due_date.month,entry.due_date.day)); self.notes.setPlainText(entry.notes or ""); self.recurring.hide(); self.recurrence_count.hide(); form.labelForField(self.recurring).hide(); form.labelForField(self.recurrence_count).hide()
        root.addLayout(form); buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel); buttons.button(QDialogButtonBox.StandardButton.Save).setText("Salvar"); buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar"); buttons.accepted.connect(self._accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)
    def _accept(self):
        try:self.data=FinancialInput(kind=self.kind.currentData(),description=self.description.text(),category=self.category.text(),amount=parse_money(self.amount.text(),True),due_date=self.due.date().toPython(),notes=self.notes.toPlainText() or None,recurring=self.recurring.isChecked(),recurrence_count=self.recurrence_count.value()); self.accept()
        except Exception as exc:QMessageBox.warning(self,"Dados inválidos",str(exc))
class FinanceView(QWidget):
    def __init__(self,session,service,parent=None):
        super().__init__(parent); self.session=session; self.service=service; self.entries=[]; root=QVBoxLayout(self); title=QLabel("Financeiro"); title.setObjectName("pageTitle"); root.addWidget(title); self.summary=QLabel(); self.summary.setObjectName("metricValue"); root.addWidget(self.summary); actions=QHBoxLayout(); self.kind=QComboBox(); self.kind.addItem("Todos",None)
        for kind,label in KIND_LABELS.items():self.kind.addItem(label,kind)
        self.status=QComboBox(); self.status.addItem("Todos os status",None)
        for status,label in STATUS_LABELS.items():self.status.addItem(label,status)
        self.kind.currentIndexChanged.connect(self.refresh); self.status.currentIndexChanged.connect(self.refresh); new=QPushButton("Novo lançamento"); new.clicked.connect(self._new); edit=QPushButton("Editar despesa"); edit.clicked.connect(self._edit_expense); delete=QPushButton("Excluir despesa"); delete.clicked.connect(self._delete_expense); pay=QPushButton("Registrar pagamento"); pay.clicked.connect(self._pay); refresh=QPushButton("Atualizar"); refresh.clicked.connect(self.refresh)
        for w in (self.kind,self.status,new,edit,delete,pay,refresh):actions.addWidget(w)
        actions.addStretch(); root.addLayout(actions)
        if Permission.FINANCE_MANAGE not in session.permissions:new.hide(); edit.hide(); delete.hide(); pay.hide()
        self.table=QTableWidget(0,8); self.table.setHorizontalHeaderLabels(["Tipo","Descrição","Categoria","Vencimento","Original","Pago","Saldo","Status"]); self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection); root.addWidget(self.table); self.refresh()
    def _text(self,title,label):
        value,ok=QInputDialog.getText(self,title,label); return value.strip() if ok else None
    def _new(self):
        dialog=FinancialEntryDialog(self)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        try:self.service.create(self.session,dialog.data); self.refresh()
        except Exception as exc:QMessageBox.warning(self,"Lançamento",str(exc))
    def _selected(self):
        row=self.table.currentRow(); return self.entries[row] if 0<=row<len(self.entries) else None
    def _expense(self):
        entry=self._selected()
        if not entry:QMessageBox.information(self,"Despesa","Selecione uma despesa."); return None
        if entry.kind!=FinancialKind.EXPENSE:QMessageBox.warning(self,"Despesa","Esta operação está disponível somente para despesas."); return None
        if entry.status!=FinancialStatus.OPEN or entry.paid_amount!=Decimal("0"):QMessageBox.warning(self,"Despesa","Somente despesas abertas e sem pagamentos podem ser alteradas."); return None
        return entry
    def _edit_expense(self):
        entry=self._expense()
        if not entry:return
        dialog=FinancialEntryDialog(self,entry)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        try:self.service.update_expense(self.session,entry.id,dialog.data); self.refresh()
        except Exception as exc:QMessageBox.warning(self,"Despesa não editada",str(exc))
    def _delete_expense(self):
        rows=sorted({index.row() for index in self.table.selectionModel().selectedRows()}); entries=[self.entries[row] for row in rows if 0<=row<len(self.entries)]
        if not entries:QMessageBox.information(self,"Excluir despesas","Selecione uma ou mais despesas."); return
        invalid=[entry for entry in entries if entry.kind!=FinancialKind.EXPENSE or entry.status!=FinancialStatus.OPEN or entry.paid_amount!=Decimal("0")]
        if invalid:QMessageBox.warning(self,"Excluir despesas","Selecione somente despesas abertas e sem pagamentos."); return
        if QMessageBox.question(self,"Excluir despesas",f"Excluir {len(entries)} despesa(s) selecionada(s)?\n\nElas serão retiradas da lista e preservadas na auditoria.")!=QMessageBox.StandardButton.Yes:return
        reason=self._text("Excluir despesas","Motivo da exclusão:")
        if reason is None:return
        try:count=self.service.delete_expenses(self.session,entries,reason); self.refresh(); QMessageBox.information(self,"Despesas excluídas",f"{count} despesa(s) excluída(s).")
        except Exception as exc:QMessageBox.warning(self,"Despesas não excluídas",str(exc))
    def _pay(self):
        entry=self._selected()
        if not entry:QMessageBox.information(self,"Pagamento","Selecione um lançamento."); return
        amount=self._text("Registrar pagamento",f"Valor (saldo {brl(entry.balance)}):")
        if amount is None:return
        method=self._text("Registrar pagamento","Forma de pagamento:")
        if method is None:return
        try:self.service.pay(self.session,entry.kind,entry.id,PaymentInput(amount=parse_money(amount,True),payment_date=date.today(),payment_method=method)); self.refresh()
        except Exception as exc:QMessageBox.warning(self,"Pagamento",str(exc))
    def refresh(self):
        try:self.entries=self.service.list(self.session,self.kind.currentData(),self.status.currentData()); totals=self.service.summary(self.session); self.summary.setText(f"A pagar: {brl(totals['pagar'])}   |   A receber: {brl(totals['receber'])}   |   Despesas: {brl(totals['despesas'])}   |   Receitas: {brl(totals['receitas'])}")
        except Exception as exc:QMessageBox.warning(self,"Financeiro",str(exc)); return
        self.table.setRowCount(len(self.entries))
        for row,e in enumerate(self.entries):
            for col,value in enumerate((KIND_LABELS[e.kind],e.description,e.category,e.due_date.strftime("%d/%m/%Y"),brl(e.original_amount),brl(e.paid_amount),brl(e.balance),STATUS_LABELS[e.status])):self.table.setItem(row,col,QTableWidgetItem(str(value)))
        self.table.resizeColumnsToContents()
