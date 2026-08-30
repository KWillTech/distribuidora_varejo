"""PDV rápido para venda por unidade e fardo."""
from decimal import Decimal
from PySide6.QtCore import QEvent,Qt,QStringListModel
from PySide6.QtWidgets import QComboBox,QCompleter,QFormLayout,QGraphicsOpacityEffect,QHBoxLayout,QInputDialog,QLabel,QLineEdit,QMessageBox,QPushButton,QSpinBox,QTableWidget,QTableWidgetItem,QVBoxLayout,QWidget
from dialogs.catalog_dialogs import parse_money
from dialogs.payment_dialog import PaymentDialog
from models.auth import AuthenticatedSession,Permission
from models.cash import CashCloseInput
from models.catalog import PackageType
from models.sale import SaleInput,SaleItem
from services.catalog import CatalogService
from services.sales import SaleService
from views.dashboard_view import brl
from utils.resources import logo_pixmap

class PosView(QWidget):
    def __init__(self,session:AuthenticatedSession,catalog:CatalogService,sales:SaleService,parent=None,customers=None,credit=None,commands=None):
        super().__init__(parent); self.session=session; self.catalog=catalog; self.sales=sales; self.customers=customers; self.credit=credit; self.commands=commands; self.active_command=None; self.items=[]; self._products=[]; root=QVBoxLayout(self); title=QLabel("PDV"); title.setObjectName("pageTitle"); root.addWidget(title); command_bar=QHBoxLayout(); command_bar.addWidget(QLabel("Comanda aguardando pagamento")); self.command=QComboBox(); self.command.setMinimumWidth(360); load_command=QPushButton("Carregar comanda"); load_command.clicked.connect(self._load_command); refresh_commands=QPushButton("Atualizar comandas"); refresh_commands.clicked.connect(self._load_commands); command_bar.addWidget(self.command); command_bar.addWidget(load_command); command_bar.addWidget(refresh_commands); command_bar.addStretch(); root.addLayout(command_bar); self.command.setVisible(commands is not None); load_command.setVisible(commands is not None); refresh_commands.setVisible(commands is not None); self.customer=QComboBox(); self.customer.addItem("Sem cliente",None); self.customer.hide(); self._load_customers(); self._load_commands()
        self.cash_warning=QLabel("Sangria obrigatória: o caixa atingiu R$ 500,00. Realize uma sangria antes de fazer outra venda."); self.cash_warning.setObjectName("warningBanner"); self.cash_warning.setWordWrap(True); self.cash_warning.setStyleSheet("QLabel { background: #7a2600; color: #ffffff; border: 1px solid #ff8a00; border-radius: 5px; padding: 9px; font-weight: 700; }"); self.cash_warning.hide(); root.addWidget(self.cash_warning); self.cash_status=QLabel(); self.cash_status.setObjectName("metricValue"); root.addWidget(self.cash_status); cash_actions=QHBoxLayout(); open_cash=QPushButton("Abrir caixa"); open_cash.clicked.connect(self._open_cash); supply=QPushButton("Suprimento"); supply.clicked.connect(self._cash_supply); withdraw=QPushButton("Sangria"); withdraw.clicked.connect(self._cash_withdraw); close_cash=QPushButton("Fechar caixa"); close_cash.clicked.connect(self._close_cash); refresh_cash=QPushButton("Atualizar"); refresh_cash.clicked.connect(self._refresh_cash_controls)
        if Permission.CASH_OPEN not in session.permissions:open_cash.hide(); supply.hide()
        if Permission.CASH_WITHDRAW not in session.permissions:withdraw.hide()
        if Permission.CASH_CLOSE not in session.permissions:close_cash.hide()
        for button in (open_cash,supply,withdraw,close_cash,refresh_cash):cash_actions.addWidget(button)
        cash_actions.addStretch(); root.addLayout(cash_actions); bar=QHBoxLayout()
        self.barcode=QLineEdit(); self.barcode.setPlaceholderText("Digite ou leia o código"); self.barcode.setMaximumWidth(230); self.barcode.returnPressed.connect(self._barcode_entered)
        self.product=QLineEdit(); self.product.setPlaceholderText("Digite o nome do produto"); self.product.setMinimumWidth(500); self.product_model=QStringListModel(); self.product_completer=QCompleter(self.product_model,self); self.product_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive); self.product_completer.setFilterMode(Qt.MatchFlag.MatchContains); self.product_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion); self.product.setCompleter(self.product_completer); self.product.textChanged.connect(self._product_changed)
        self.package=QComboBox(); self.package.addItem("Unidade",PackageType.UNIT); self.package.addItem("Fardo",PackageType.PACK); self.quantity=QSpinBox(); self.quantity.setRange(1,100000); add=QPushButton("Adicionar"); add.clicked.connect(self._add)
        for label,widget,stretch in (("Código de barras",self.barcode,1),("Produto",self.product,3),("Unidade/Fardo",self.package,1),("Quantidade",self.quantity,1)):
            field=QVBoxLayout(); field.addWidget(QLabel(label)); field.addWidget(widget); bar.addLayout(field,stretch)
        bar.addWidget(add); root.addLayout(bar)
        self.table=QTableWidget(0,6); self.table.setHorizontalHeaderLabels(["Produto","Tipo","Qtd.","Unidades","Preço","Total"]); root.addWidget(self.table)
        self.watermark=QLabel(self.table.viewport()); self.watermark.setPixmap(logo_pixmap(360,360)); self.watermark.setScaledContents(False); self.watermark.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents); opacity=QGraphicsOpacityEffect(self.watermark); opacity.setOpacity(0.09); self.watermark.setGraphicsEffect(opacity); self.watermark.adjustSize(); self.table.viewport().installEventFilter(self); self._position_watermark()
        controls=QHBoxLayout(); remove=QPushButton("Remover"); remove.clicked.connect(self._remove); controls.addWidget(remove); self.discount=QLineEdit("0,00"); self.surcharge=QLineEdit("0,00"); controls.addWidget(QLabel("Desconto")); controls.addWidget(self.discount); controls.addWidget(QLabel("Acréscimo")); controls.addWidget(self.surcharge); self.total_label=QLabel("Total: R$ 0,00"); self.total_label.setObjectName("metricValue"); controls.addStretch(); controls.addWidget(self.total_label); root.addLayout(controls); finish=QPushButton("Finalizar venda (F10)"); finish.clicked.connect(self._finish); finish.setShortcut("F10"); root.addWidget(finish); self._load()
    def eventFilter(self, watched, event):
        if watched is self.table.viewport() and event.type() in (QEvent.Type.Resize,QEvent.Type.Show): self._position_watermark()
        return super().eventFilter(watched,event)
    def _position_watermark(self):
        if not hasattr(self,"watermark"): return
        area=self.table.viewport().rect(); size=self.watermark.size(); self.watermark.move(max(0,(area.width()-size.width())//2),max(0,(area.height()-size.height())//2)); self.watermark.raise_()
    def _load(self):
        try:
            self._products=self.catalog.pos_products(self.session); self.product_model.setStringList([p.name for p in self._products]); self.product.clear()
            self._product_changed()
        except Exception as exc: QMessageBox.warning(self,"PDV",str(exc))
        self._refresh_cash_controls()
    def _load_customers(self):
        if not self.customers:return
        try:
            result=self.customers.list_page(self.session,active=True,page=1,page_size=100)
            for customer in result.items:self.customer.addItem(f"{customer.full_name or 'Sem nome'} — {customer.cpf or customer.phone or ''}",customer)
        except Exception:pass
    def _load_commands(self):
        if not self.commands:return
        selected=self.active_command.id if self.active_command else None; self.command.clear(); self.command.addItem("Selecione uma comanda",None)
        try:
            for command in self.commands.list(self.session,status="aguardando_pagamento"):self.command.addItem(f"{command.number} — {command.identification} — {brl(command.total)}",command)
            if selected:
                for index in range(self.command.count()):
                    value=self.command.itemData(index)
                    if value and value.id==selected:self.command.setCurrentIndex(index); break
        except Exception as exc:QMessageBox.warning(self,"Comandas",str(exc))
    def _load_command(self):
        command=self.command.currentData()
        if not command:QMessageBox.information(self,"PDV","Selecione uma comanda aguardando pagamento."); return
        self.active_command=command; self.items=[SaleItem(product_id=i.product_id,product_name=i.product_name,package_type=i.package_type,quantity=i.quantity,units_per_pack=i.units_per_pack,unit_price=i.price,discount=i.discount) for i in command.items]; self.discount.setText(str(command.discount).replace(".",",")); self.surcharge.setText(str(command.surcharge).replace(".",",")); self.customer.setCurrentIndex(0)
        for index in range(self.customer.count()):
            customer=self.customer.itemData(index)
            if customer and customer.id==command.customer_id:self.customer.setCurrentIndex(index); break
        self._refresh(); QMessageBox.information(self,"Comanda carregada",f"{command.number} pronta para receber o pagamento.")
    def showEvent(self,event):
        super().showEvent(event); self._refresh_cash_controls(); self._load_commands()
    def _refresh_cash_warning(self):
        cash=getattr(self.sales,"cash",None)
        if not cash: self.cash_warning.hide(); return
        try:self.cash_warning.setVisible(cash.withdrawal_required(self.session))
        except Exception:self.cash_warning.hide()
    def _money(self,title,label,positive=True):
        text,ok=QInputDialog.getText(self,title,label)
        if not ok:return None
        try:return parse_money(text,positive)
        except ValueError as exc:QMessageBox.warning(self,title,str(exc)); return None
    def _refresh_cash_controls(self):
        cash=getattr(self.sales,"cash",None)
        if not cash:self.cash_status.setText("Caixa indisponível"); return
        try:current=cash.current(self.session); self.cash_status.setText(f"Caixa aberto — saldo esperado: {brl(current.expected_amount)}" if current else "Nenhum caixa aberto"); self._refresh_cash_warning()
        except Exception as exc:QMessageBox.warning(self,"Caixa",str(exc))
    def _open_cash(self):
        amount=self._money("Abrir caixa","Valor inicial:",False)
        if amount is None:return
        try:self.sales.cash.open(self.session,amount); self._refresh_cash_controls()
        except Exception as exc:QMessageBox.warning(self,"Caixa",str(exc))
    def _cash_supply(self):self._cash_movement("Suprimento",self.sales.cash.supply)
    def _cash_withdraw(self):self._cash_movement("Sangria",self.sales.cash.withdraw)
    def _cash_movement(self,title,operation):
        amount=self._money(title,"Valor:")
        if amount is None:return
        reason,ok=QInputDialog.getText(self,title,"Motivo:")
        if not ok or len(reason.strip())<3:QMessageBox.warning(self,title,"Informe o motivo."); return
        try:operation(self.session,amount,reason); self._refresh_cash_controls()
        except Exception as exc:QMessageBox.warning(self,title,str(exc))
    def _close_cash(self):
        counted=self._money("Fechar caixa","Valor contado:",False)
        if counted is None:return
        current=self.sales.cash.current(self.session)
        if not current:QMessageBox.warning(self,"Fechar caixa","Não há caixa aberto."); return
        justification=None
        if counted!=current.expected_amount:
            justification,ok=QInputDialog.getText(self,"Diferença de caixa",f"Esperado: {brl(current.expected_amount)}\nDiferença: {brl(counted-current.expected_amount)}\nJustificativa:")
            if not ok:return
        try:self.sales.cash.close(self.session,CashCloseInput(counted_amount=counted,justification=justification)); self._refresh_cash_controls()
        except Exception as exc:QMessageBox.warning(self,"Fechar caixa",str(exc))
    def _product_changed(self):
        p=self._selected(); pack_item=self.package.model().item(1)
        if pack_item: pack_item.setEnabled(bool(p and p.units_per_pack and p.pack_price is not None))
        if p and (not p.units_per_pack or p.pack_price is None): self.package.setCurrentIndex(0)
    def _barcode_entered(self):
        code=self.barcode.text().strip()
        if not code:return
        for p in self._products:
            if code==p.unit_barcode or code==p.pack_barcode:
                self.product.setText(p.name); self.package.setCurrentIndex(1 if code==p.pack_barcode else 0); self.quantity.setFocus(); self.quantity.selectAll(); return
        QMessageBox.warning(self,"Código de barras","Código de barras não encontrado."); self.barcode.selectAll()
    def _selected(self):
        text=self.product.text().casefold().strip()
        for p in self._products:
            if text==p.name.casefold(): return p
        return None
    def _add(self):
        if self.active_command:QMessageBox.information(self,"PDV","Esta comanda já foi fechada. Os itens não podem ser alterados no PDV."); return
        p=self._selected(); package=self.package.currentData()
        if not p: QMessageBox.warning(self,"PDV","Selecione um produto."); return
        if package==PackageType.PACK and (not p.units_per_pack or p.pack_price is None): QMessageBox.warning(self,"PDV","Produto não configurado para venda por fardo."); return
        price=(p.promotional_pack_price or p.pack_price) if package==PackageType.PACK else (p.promotional_unit_price or p.unit_price); self.items.append(SaleItem(product_id=p.id or "",product_name=p.name,package_type=package,quantity=self.quantity.value(),units_per_pack=p.units_per_pack,unit_price=price)); self.barcode.clear(); self.quantity.setValue(1); self.barcode.setFocus(); self._refresh()
    def _remove(self):
        if self.active_command:QMessageBox.information(self,"PDV","Itens de uma comanda fechada não podem ser removidos no PDV."); return
        row=self.table.currentRow()
        if row>=0: self.items.pop(row); self._refresh()
    def _total(self): return self.active_command.total if self.active_command else sum((i.total for i in self.items),Decimal("0"))-(parse_money(self.discount.text()) or Decimal("0"))+(parse_money(self.surcharge.text()) or Decimal("0"))
    def _refresh(self):
        self.table.setRowCount(len(self.items))
        for row,i in enumerate(self.items):
            for col,v in enumerate((i.product_name,i.package_type.value.title(),i.quantity,i.converted_units,brl(i.unit_price),brl(i.total))): self.table.setItem(row,col,QTableWidgetItem(str(v)))
        try:self.total_label.setText(f"Total: {brl(self._total())}")
        except ValueError:self.total_label.setText("Total inválido")
    def _finish(self):
        cash=getattr(self.sales,"cash",None)
        if cash:
            try:cash.require_sale_allowed(self.session)
            except Exception as exc:
                self._refresh_cash_warning(); QMessageBox.warning(self,"Sangria obrigatória",str(exc)); return
        try: total=self._total()
        except ValueError as exc: QMessageBox.warning(self,"PDV",str(exc)); return
        customer=self.customer.currentData(); dialog=PaymentDialog(total,self,customer,self.session,self.credit)
        if dialog.exec()!=dialog.DialogCode.Accepted:return
        try:
            if self.active_command:
                command=self.commands.finalize(self.session,self.active_command.id,self.active_command.version,dialog.payments,dialog.due.date().toPython() if any(p.method.value=="fiado" for p in dialog.payments) else None,dialog.allow_overdue.isChecked(),dialog.allow_limit.isChecked(),dialog.justification.text() or None); QMessageBox.information(self,"Pagamento concluído",f"Comanda {command.number} paga e finalizada.\nTotal: {brl(command.total)}")
            else:
                data=SaleInput(customer_id=customer.id if customer else None,customer_name=customer.full_name if customer else None,items=self.items,total_discount=parse_money(self.discount.text()) or Decimal("0"),surcharge=parse_money(self.surcharge.text()) or Decimal("0"),payments=dialog.payments,credit_due_date=dialog.due.date().toPython() if any(p.method.value=="fiado" for p in dialog.payments) else None,credit_allow_overdue=dialog.allow_overdue.isChecked(),credit_allow_over_limit=dialog.allow_limit.isChecked(),credit_justification=dialog.justification.text() or None); sale=self.sales.finalize(self.session,data); QMessageBox.information(self,"Venda concluída",f"Venda {sale.number} concluída.\nTotal: {brl(sale.total)}\nTroco: {brl(sale.change)}")
            self.active_command=None; self.items=[]; self.discount.setText("0,00"); self.surcharge.setText("0,00"); self._refresh(); self._load(); self._load_commands()
        except Exception as exc: QMessageBox.warning(self,"Venda não concluída",str(exc))
