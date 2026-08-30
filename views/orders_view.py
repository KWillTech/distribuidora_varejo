"""Tela operacional de pedidos e entregas."""
from decimal import Decimal
from PySide6.QtWidgets import QComboBox,QHBoxLayout,QInputDialog,QLabel,QMessageBox,QPushButton,QTableWidget,QTableWidgetItem,QVBoxLayout,QWidget
from dialogs.catalog_dialogs import parse_money
from models.auth import Permission
from models.order import OrderInput,OrderStatus,STATUS_LABELS

class OrdersView(QWidget):
    def __init__(self,session,service,parent=None):
        super().__init__(parent); self.session=session; self.service=service; self.orders=[]; root=QVBoxLayout(self); title=QLabel("Pedidos e entregas"); title.setObjectName("pageTitle"); root.addWidget(title); actions=QHBoxLayout(); new=QPushButton("Novo pedido"); new.clicked.connect(self._new); assign=QPushButton("Atribuir entregador"); assign.clicked.connect(self._assign); occurrence=QPushButton("Registrar ocorrência"); occurrence.clicked.connect(self._occurrence); self.status=QComboBox()
        for status,label in STATUS_LABELS.items():self.status.addItem(label,status)
        update=QPushButton("Atualizar status"); update.clicked.connect(self._status); refresh=QPushButton("Atualizar"); refresh.clicked.connect(self.refresh)
        for widget in (new,assign,occurrence,self.status,update,refresh):actions.addWidget(widget)
        actions.addStretch(); root.addLayout(actions)
        if not ({Permission.DELIVERIES_MANAGE,Permission.ORDERS_CREATE}&session.permissions):new.hide()
        if Permission.DELIVERIES_MANAGE not in session.permissions:assign.hide()
        self.table=QTableWidget(0,8); self.table.setHorizontalHeaderLabels(["Pedido","Cliente","Telefone","Volumes","Pagamento","Entregador","Status","Data"]); self.table.itemSelectionChanged.connect(self._selection); root.addWidget(self.table); self.details=QLabel("Selecione um pedido para exibir endereço, produtos e ocorrências."); self.details.setWordWrap(True); root.addWidget(self.details); self.refresh()
    def _text(self,title,label,required=True):
        value,ok=QInputDialog.getText(self,title,label)
        if not ok:return None
        value=value.strip()
        if required and not value:QMessageBox.warning(self,title,"Campo obrigatório."); return None
        return value
    def _new(self):
        values=[]
        for label in ("Cliente:","Telefone:","Endereço completo:","Referência (opcional):","Produtos e quantidades:"):
            value=self._text("Novo pedido",label,label!="Referência (opcional):")
            if value is None:return
            values.append(value)
        volumes,ok=QInputDialog.getInt(self,"Novo pedido","Quantidade de volumes:",1,1,10000)
        if not ok:return
        fee=self._text("Novo pedido","Taxa de entrega (R$):")
        if fee is None:return
        payment=self._text("Novo pedido","Forma de pagamento:")
        if payment is None:return
        change=self._text("Novo pedido","Troco para (opcional):",False)
        if change is None:return
        notes=self._text("Novo pedido","Observações (opcional):",False)
        if notes is None:return
        try:self.service.create(self.session,OrderInput(customer_name=values[0],phone=values[1],address=values[2],reference=values[3] or None,products=values[4],volumes=volumes,delivery_fee=parse_money(fee) or Decimal("0"),payment_method=payment,change_for=parse_money(change) if change else None,notes=notes or None)); self.refresh()
        except Exception as exc:QMessageBox.warning(self,"Pedido não criado",str(exc))
    def _selected(self):
        row=self.table.currentRow(); return self.orders[row] if 0<=row<len(self.orders) else None
    def _assign(self):
        order=self._selected()
        if not order:QMessageBox.information(self,"Entregador","Selecione um pedido."); return
        name=self._text("Atribuir entregador","Nome ou usuário do entregador:")
        if name is None:return
        try:self.service.assign(self.session,order.id or "",name,name); self.refresh()
        except Exception as exc:QMessageBox.warning(self,"Entregador",str(exc))
    def _status(self):
        order=self._selected()
        if not order:QMessageBox.information(self,"Status","Selecione um pedido."); return
        try:self.service.update_status(self.session,order.id or "",self.status.currentData()); self.refresh()
        except Exception as exc:QMessageBox.warning(self,"Status não alterado",str(exc))
    def _occurrence(self):
        order=self._selected()
        if not order:QMessageBox.information(self,"Ocorrência","Selecione um pedido."); return
        text=self._text("Ocorrência","Descreva a ocorrência:")
        if text is None:return
        try:self.service.occurrence(self.session,order.id or "",text); self.refresh()
        except Exception as exc:QMessageBox.warning(self,"Ocorrência",str(exc))
    def refresh(self):
        try:self.orders=self.service.list(self.session); self.table.setRowCount(len(self.orders))
        except Exception as exc:QMessageBox.warning(self,"Pedidos",str(exc)); return
        for row,o in enumerate(self.orders):
            for col,value in enumerate((o.number,o.customer_name,o.phone,o.volumes,o.payment_method,o.delivery_person_name or "—",STATUS_LABELS[o.status],o.created_at.strftime("%d/%m/%Y %H:%M"))):self.table.setItem(row,col,QTableWidgetItem(str(value)))
        self.table.resizeColumnsToContents(); self._selection()
    def _selection(self):
        order=self._selected()
        if not order:self.details.setText("Selecione um pedido para exibir endereço, produtos e ocorrências."); return
        occurrences="\n".join(order.occurrences) or "Nenhuma"
        self.details.setText(f"Endereço: {order.address}\nReferência: {order.reference or '—'}\nProdutos: {order.products}\nTaxa: R$ {order.delivery_fee:.2f} | Troco para: {order.change_for if order.change_for is not None else '—'}\nObservações: {order.notes or '—'}\nOcorrências:\n{occurrences}")
