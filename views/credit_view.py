"""Central de fiado, contas, recebimentos e extrato do cliente."""
from decimal import Decimal
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView,QComboBox,QDialog,QDialogButtonBox,QFormLayout,QGridLayout,QHBoxLayout,QInputDialog,QLabel,QLineEdit,QMessageBox,QPushButton,QTabWidget,QTableWidget,QTableWidgetItem,QVBoxLayout,QWidget
from dialogs.catalog_dialogs import parse_money
from models.auth import Permission
from models.credit import CreditPaymentInput,ReceivableStatus
from views.dashboard_view import brl
from widgets.metric_card import MetricCard

STATUS={"pendente":"Pendente","parcialmente_pago":"Parcial","pago":"Pago","vencido":"Vencido","renegociado":"Renegociado","cancelado":"Cancelado"}
class ReceiveCreditDialog(QDialog):
    def __init__(self,customer,accounts,parent=None):
        super().__init__(parent); self.customer=customer; self.accounts=accounts; self.setWindowTitle("Receber Fiado"); self.resize(760,520); root=QVBoxLayout(self); root.addWidget(QLabel(f"Cliente: {customer.full_name or 'Sem nome'} | Saldo total: {brl(sum((a.open_balance for a in accounts),Decimal('0')))}")); self.table=QTableWidget(len(accounts),5); self.table.setHorizontalHeaderLabels(["Conta","Venda","Vencimento","Saldo","Status"]); self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        for row,a in enumerate(accounts):
            for col,value in enumerate((a.id,a.sale_number,a.due_date.strftime("%d/%m/%Y"),brl(a.open_balance),STATUS[a.status.value])):self.table.setItem(row,col,QTableWidgetItem(str(value)))
        root.addWidget(self.table); form=QFormLayout(); self.amount=QLineEdit(); self.amount.setPlaceholderText("0,00"); self.method=QComboBox(); self.method.addItems(["Dinheiro","Pix","Débito","Crédito"]); self.notes=QLineEdit(); form.addRow("Valor do pagamento",self.amount); form.addRow("Forma",self.method); form.addRow("Observação",self.notes); root.addLayout(form); buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel); buttons.button(QDialogButtonBox.StandardButton.Save).setText("Confirmar recebimento"); buttons.accepted.connect(self._accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)
    def _accept(self):
        try:
            rows=sorted({index.row() for index in self.table.selectionModel().selectedRows()}); ids=[self.accounts[row].id for row in rows] if rows else []; self.data=CreditPaymentInput(amount=parse_money(self.amount.text(),True),payment_method=self.method.currentText().lower().replace("é","e"),notes=self.notes.text() or None,account_ids=ids); self.accept()
        except Exception as exc:QMessageBox.warning(self,"Pagamento inválido",str(exc))

class CreditView(QWidget):
    def __init__(self,session,service,customers,parent=None):
        super().__init__(parent); self.session=session; self.service=service; self.customers=customers; self.accounts=[]; self.customer_items=[]; root=QVBoxLayout(self); title=QLabel("Fiado"); title.setObjectName("pageTitle"); root.addWidget(title); cards=QGridLayout(); self.cards={}
        metrics=(("total","Total a receber"),("overdue","Total vencido"),("received_today","Recebido hoje"),("received_month","Recebido no mês"),("customers","Clientes com dívida"),("delinquent","Clientes inadimplentes"),("limit_granted","Limite concedido"),("limit_used","Limite utilizado"))
        for index,(key,label) in enumerate(metrics):card=MetricCard(label); self.cards[key]=card; cards.addWidget(card,index//4,index%4)
        root.addLayout(cards); filters=QHBoxLayout(); self.customer=QComboBox(); self.customer.addItem("Todos os clientes",None); self.customer.currentIndexChanged.connect(self.refresh); refresh=QPushButton("Atualizar"); refresh.clicked.connect(self.refresh); receive=QPushButton("Receber Fiado"); receive.clicked.connect(self._receive); extract=QPushButton("Extrato do cliente"); extract.clicked.connect(self._extract); block=QPushButton("Bloquear/Desbloquear"); block.clicked.connect(self._block)
        for w in (self.customer,refresh,receive,extract,block):filters.addWidget(w)
        filters.addStretch(); root.addLayout(filters)
        if Permission.CREDIT_RECEIVE not in session.permissions:receive.hide()
        if not ({Permission.CREDIT_BLOCK,Permission.CREDIT_UNBLOCK}&session.permissions):block.hide()
        tabs=QTabWidget(); open_page=QWidget(); open_layout=QVBoxLayout(open_page); self.table=QTableWidget(0,10); self.table.setHorizontalHeaderLabels(["Cliente","Telefone","Venda","Compra","Vencimento","Original","Pago","Saldo","Atraso","Status"]); self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); open_layout.addWidget(self.table); tabs.addTab(open_page,"Contas em aberto"); self.payments_table=QTableWidget(0,8); self.payments_table.setHorizontalHeaderLabels(["Data","Cliente","Valor","Forma","Contas","Caixa","Usuário","Observação"]); tabs.addTab(self.payments_table,"Recebimentos"); self.movements=QTableWidget(0,7); self.movements.setHorizontalHeaderLabels(["Data","Cliente","Conta","Tipo","Valor","Forma","Usuário"]); tabs.addTab(self.movements,"Extrato do cliente"); root.addWidget(tabs); self._load_customers(); self.refresh()
    def _load_customers(self):
        try:
            result=self.customers.list_page(self.session,active=None,page=1,page_size=100); self.customer_items=result.items
            for customer in result.items:self.customer.addItem(customer.full_name or customer.cpf or customer.phone or "Cliente",customer)
        except Exception:pass
    def refresh(self):
        selected=self.customer.currentData(); customer_id=selected.id if selected else None
        try:self.accounts=self.service.list_accounts(self.session,customer_id); summary=self.service.summary(self.session)
        except Exception as exc:QMessageBox.warning(self,"Fiado",str(exc)); return
        self.cards["total"].set_value(brl(summary["total"])); self.cards["overdue"].set_value(brl(summary["overdue"])); self.cards["received_today"].set_value(brl(summary["received_today"])); self.cards["received_month"].set_value(brl(summary["received_month"])); self.cards["customers"].set_value(str(summary["customers"])); self.cards["delinquent"].set_value(str(summary["delinquent"])); self.cards["limit_granted"].set_value(brl(summary["limit_granted"])); self.cards["limit_used"].set_value(brl(summary["limit_used"])); self.table.setRowCount(len(self.accounts))
        from datetime import date
        for row,a in enumerate(self.accounts):
            customer=next((c for c in self.customer_items if c.id==a.customer_id),None); delay=max(0,(date.today()-a.due_date).days); values=(a.customer_name,customer.phone if customer else "",a.sale_number,a.sale_date.strftime("%d/%m/%Y"),a.due_date.strftime("%d/%m/%Y"),brl(a.original_amount),brl(a.paid_amount),brl(a.open_balance),delay,STATUS[a.status.value])
            for col,value in enumerate(values):self.table.setItem(row,col,QTableWidgetItem(str(value)))
        self.table.resizeColumnsToContents(); self._load_payments(customer_id); self._load_movements(customer_id)
    def _load_payments(self,customer_id):
        rows=self.service.payments(self.session,customer_id); self.payments_table.setRowCount(len(rows))
        for row,p in enumerate(rows):
            value=p["valor"].to_decimal() if hasattr(p["valor"],"to_decimal") else Decimal(str(p["valor"])); customer=next((c for c in self.customer_items if c.id==p.get("cliente_id")),None); values=(p["data_hora"].strftime("%d/%m/%Y %H:%M"),customer.full_name if customer else "",brl(value),p.get("forma_pagamento","").title(),", ".join(x.get("conta_id","") for x in p.get("contas",[])),p.get("caixa_id") or "—",p.get("usuario",""),p.get("observacao") or "—")
            for col,item in enumerate(values):self.payments_table.setItem(row,col,QTableWidgetItem(str(item)))
    def _load_movements(self,customer_id):
        if not customer_id:self.movements.setRowCount(0); return
        rows=self.service.movements(self.session,customer_id); self.movements.setRowCount(len(rows)); customer=self.customer.currentData()
        for row,m in enumerate(rows):
            values=(m["data_hora"].strftime("%d/%m/%Y %H:%M"),customer.full_name or "",m.get("conta_receber_id",""),m["tipo"].replace("_"," ").title(),brl(m["valor"].to_decimal()),m.get("forma_pagamento") or "—",m.get("usuario",""))
            for col,value in enumerate(values):self.movements.setItem(row,col,QTableWidgetItem(str(value)))
    def _receive(self):
        customer=self.customer.currentData()
        if not customer:QMessageBox.information(self,"Receber Fiado","Selecione um cliente."); return
        accounts=[a for a in self.accounts if a.open_balance>0]
        if not accounts:QMessageBox.information(self,"Receber Fiado","Cliente sem contas em aberto."); return
        dialog=ReceiveCreditDialog(customer,accounts,self)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        try:payment=self.service.receive(self.session,customer.id or "",dialog.data); QMessageBox.information(self,"Recebimento concluído",f"Pagamento {payment} registrado com sucesso."); self.refresh()
        except Exception as exc:QMessageBox.warning(self,"Recebimento não realizado",str(exc))
    def _extract(self):
        customer=self.customer.currentData()
        if not customer:QMessageBox.information(self,"Extrato","Selecione um cliente."); return
        rows=self.service.movements(self.session,customer.id or ""); lines=[f"Extrato - {customer.full_name}",""]+[f"{m['data_hora']:%d/%m/%Y %H:%M} | {m['tipo'].replace('_',' ').title()} | {brl(m['valor'].to_decimal())} | Saldo: {brl(m['saldo_posterior'].to_decimal())}" for m in rows]; QMessageBox.information(self,"Extrato do cliente","\n".join(lines) if rows else "Nenhuma movimentação.")
    def _block(self):
        customer=self.customer.currentData()
        if not customer:QMessageBox.information(self,"Fiado","Selecione um cliente."); return
        blocked=customer.credit.status.value!="bloqueado_manual"; reason,ok=QInputDialog.getText(self,"Bloquear cliente" if blocked else "Desbloquear cliente","Motivo:")
        if not ok:return
        try:self.service.block_customer(self.session,customer.id or "",blocked,reason); self.customer.clear(); self.customer.addItem("Todos os clientes",None); self._load_customers(); self.refresh()
        except Exception as exc:QMessageBox.warning(self,"Fiado",str(exc))
