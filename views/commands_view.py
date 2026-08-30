"""Tela principal e detalhes operacionais das comandas."""
from datetime import datetime,timezone
from decimal import Decimal
from PySide6.QtCore import Qt,QTimer,QStringListModel
from PySide6.QtWidgets import QAbstractItemView,QComboBox,QCompleter,QDialog,QDialogButtonBox,QFileDialog,QFormLayout,QGridLayout,QHBoxLayout,QInputDialog,QLabel,QLineEdit,QMessageBox,QPushButton,QSpinBox,QTabWidget,QTableWidget,QTableWidgetItem,QVBoxLayout,QWidget
from models.auth import Permission
from models.catalog import PackageType
from models.command import CommandItemInput,CommandOpenInput,CommandStatus,ServiceType
from views.dashboard_view import brl
from widgets.metric_card import MetricCard

STATUS={"aberta":"Aberta","em_atendimento":"Em atendimento","aguardando_pagamento":"Aguardando pagamento","finalizada":"Finalizada","cancelada":"Cancelada","unificada":"Unificada"}
class OpenCommandDialog(QDialog):
    def __init__(self,customers,session,parent=None,slot_number=None):
        super().__init__(parent); self.slot_number=slot_number; self.setWindowTitle(f"Abrir Comanda {slot_number:02d}" if slot_number else "Abrir Comanda"); root=QVBoxLayout(self); form=QFormLayout(); self.customer_items=[]; self.customer=QLineEdit(); self.customer.setPlaceholderText("Digite o nome do cliente (opcional)"); self.customer_model=QStringListModel(); self.customer_completer=QCompleter(self.customer_model,self); self.customer_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive); self.customer_completer.setFilterMode(Qt.MatchFlag.MatchContains); self.customer_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion); self.customer.setCompleter(self.customer_completer)
        try:
            self.customer_items=customers.list_page(session,active=True,page=1,page_size=100).items; self.customer_model.setStringList([c.full_name or c.cpf or c.phone or "Cliente" for c in self.customer_items])
        except Exception:pass
        self.identification=QLineEdit(); self.phone=QLineEdit(); self.service=QComboBox(); [self.service.addItem(label,value) for label,value in (("Balcão",ServiceType.COUNTER),("Retirada",ServiceType.PICKUP),("Entrega",ServiceType.DELIVERY))]; self.notes=QLineEdit(); self.customer.textChanged.connect(self._customer_changed); self.customer_completer.activated.connect(self._customer_changed)
        for label,widget in (("Cliente cadastrado",self.customer),("Nome/identificação",self.identification),("Telefone",self.phone),("Tipo de atendimento",self.service),("Observações",self.notes)):form.addRow(label,widget)
        root.addLayout(form); buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel); buttons.button(QDialogButtonBox.StandardButton.Save).setText("Abrir comanda"); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)
    def _selected_customer(self):
        text=self.customer.text().strip().casefold(); return next((c for c in self.customer_items if (c.full_name or "").casefold()==text),None)
    def _customer_changed(self,*_):
        c=self._selected_customer()
        if c:self.identification.setText(c.full_name or ""); self.phone.setText(c.phone or c.whatsapp or "")
    def value(self,confirm=False):
        c=self._selected_customer(); return CommandOpenInput(slot_number=self.slot_number,customer_id=c.id if c else None,customer_name=c.full_name if c else None,identification=self.identification.text() or self.customer.text() or f"Comanda {self.slot_number or ''}",phone=self.phone.text() or None,people=None,service_type=self.service.currentData(),notes=self.notes.text() or None,confirm_duplicate=confirm)
class CommandDetailDialog(QDialog):
    def __init__(self,session,service,catalog,customers,credit,command,parent=None):
        super().__init__(parent); self.session=session; self.service=service; self.catalog=catalog; self.customers=customers; self.credit=credit; self.command=command; self.products=[]; self.setWindowTitle(f"Comanda {command.number}"); self.resize(1050,700); root=QVBoxLayout(self); self.header=QLabel(); root.addWidget(self.header); bar=QHBoxLayout(); self.barcode=QLineEdit(); self.barcode.setPlaceholderText("Código de barras"); self.barcode.setMaximumWidth(220); self.barcode.returnPressed.connect(self._barcode_entered); self.product=QLineEdit(); self.product.setPlaceholderText("Digite o nome do produto"); self.product.setMinimumWidth(420); self.product_model=QStringListModel(); self.product_completer=QCompleter(self.product_model,self); self.product_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive); self.product_completer.setFilterMode(Qt.MatchFlag.MatchContains); self.product_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion); self.product.setCompleter(self.product_completer); self.package=QComboBox(); self.package.addItem("Unidade",PackageType.UNIT); self.package.addItem("Fardo",PackageType.PACK); self.quantity=QSpinBox(); self.quantity.setRange(1,100000); add=QPushButton("Adicionar"); add.clicked.connect(self._add)
        bar.addWidget(self.barcode,1); bar.addWidget(self.product,4); bar.addWidget(self.package,1); bar.addWidget(self.quantity,1); bar.addWidget(add,1)
        root.addLayout(bar); self.table=QTableWidget(0,10); self.table.setHorizontalHeaderLabels(["Código","Produto","Tipo","Qtd.","Un./fardo","Unidades","Preço","Desconto","Subtotal","Usuário"]); root.addWidget(self.table); controls=QHBoxLayout(); remove=QPushButton("Remover item"); remove.clicked.connect(self._remove); reopen=QPushButton("Voltar ao atendimento"); reopen.clicked.connect(self._reopen); finish=QPushButton("Fechar comanda e enviar ao PDV"); finish.clicked.connect(self._finish); cancel=QPushButton("Cancelar comanda"); cancel.clicked.connect(self._cancel_command); close=QPushButton("Voltar ao painel"); close.clicked.connect(self.accept)
        for w in (remove,reopen,finish,cancel,close):controls.addWidget(w)
        controls.addStretch(); root.addLayout(controls); read_only=command.status in (CommandStatus.FINALIZED,CommandStatus.CANCELLED,CommandStatus.MERGED); remove.setVisible(not read_only and Permission.TABS_REMOVE_ITEM in session.permissions); reopen.setVisible(not read_only and Permission.TABS_EDIT_ITEM in session.permissions); finish.setVisible(not read_only and Permission.TABS_REQUEST_CLOSE in session.permissions); cancel.setVisible(not read_only and Permission.TABS_CANCEL in session.permissions); add.setVisible(not read_only and Permission.TABS_ADD_ITEM in session.permissions); self._load_products(); self._refresh()
    def _load_products(self):
        try:self.products=self.catalog.pos_products(self.session); self.product_model.setStringList([p.name for p in self.products]); self.product.clear()
        except Exception:pass
    def _selected(self):
        code=self.barcode.text().strip(); text=self.product.text().strip().casefold()
        return next((p for p in self.products if code and code in (p.unit_barcode,p.pack_barcode)),None) or next((p for p in self.products if p.name.casefold()==text),None)
    def _barcode_entered(self):
        code=self.barcode.text().strip()
        if not code:return
        product=next((p for p in self.products if code in (p.unit_barcode,p.pack_barcode)),None)
        if not product:QMessageBox.warning(self,"Código de barras","Código de barras não encontrado."); self.barcode.selectAll(); return
        self.product.setText(product.name); self.package.setCurrentIndex(1 if code==product.pack_barcode else 0); self.quantity.setFocus(); self.quantity.selectAll()
    def _add(self):
        p=self._selected(); package=self.package.currentData()
        if not p:QMessageBox.warning(self,"Comanda","Produto não encontrado."); return
        if self.barcode.text()==p.pack_barcode:package=PackageType.PACK
        price=(p.promotional_pack_price or p.pack_price) if package==PackageType.PACK else (p.promotional_unit_price or p.unit_price)
        try:self.command=self.service.add_item(self.session,self.command.id,self.command.version,CommandItemInput(product_id=p.id,code=p.internal_code,product_name=p.name,package_type=package,quantity=self.quantity.value(),units_per_pack=p.units_per_pack,price=price,barcode=self.barcode.text() or None)); self.barcode.clear(); self.product.clear(); self.package.setCurrentIndex(0); self.quantity.setValue(1); self.barcode.setFocus(); self._refresh()
        except Exception as exc:QMessageBox.warning(self,"Produto não adicionado",str(exc))
    def _remove(self):
        row=self.table.currentRow()
        if row<0:return
        reason,ok=QInputDialog.getText(self,"Remover item","Motivo da remoção:")
        if ok:
            try:self.command=self.service.remove_item(self.session,self.command.id,self.command.version,self.command.items[row].item_id,reason); self._refresh()
            except Exception as exc:QMessageBox.warning(self,"Remoção",str(exc))
    def _reopen(self):
        reason,ok=QInputDialog.getText(self,"Voltar ao atendimento","Motivo:")
        if ok:
            try:self.command=self.service.reopen(self.session,self.command.id,self.command.version,reason); self._refresh()
            except Exception as exc:QMessageBox.warning(self,"Comanda",str(exc))
    def _finish(self):
        try:
            if self.command.status==CommandStatus.AWAITING_PAYMENT:QMessageBox.information(self,"Comanda",f"{self.command.number} já está disponível no PDV para pagamento."); return
            if QMessageBox.question(self,"Fechar comanda",f"Fechar {self.command.number} e enviá-la ao PDV para pagamento?")!=QMessageBox.StandardButton.Yes:return
            self.command=self.service.request_close(self.session,self.command.id,self.command.version); QMessageBox.information(self,"Comanda enviada ao PDV",f"{self.command.number} está aguardando pagamento no PDV."); self.accept()
        except Exception as exc:QMessageBox.warning(self,"Comanda não fechada",str(exc))
    def _cancel_command(self):
        if self.command.status in (CommandStatus.FINALIZED,CommandStatus.CANCELLED):QMessageBox.information(self,"Cancelar comanda","Esta comanda não pode ser cancelada."); return
        reason,ok=QInputDialog.getText(self,"Cancelar comanda","Motivo do cancelamento:")
        if not ok:return
        if len(reason.strip())<3:QMessageBox.warning(self,"Cancelar comanda","Informe o motivo do cancelamento."); return
        if QMessageBox.question(self,"Confirmar cancelamento","Cancelar a comanda e liberar todas as reservas de estoque?")!=QMessageBox.StandardButton.Yes:return
        try:self.command=self.service.cancel(self.session,self.command.id,self.command.version,reason); QMessageBox.information(self,"Comanda cancelada",f"{self.command.number} foi cancelada."); self.accept()
        except Exception as exc:QMessageBox.warning(self,"Cancelamento não concluído",str(exc))
    def _refresh(self):
        elapsed=(datetime.now(timezone.utc)-self.command.opened_at).total_seconds()/60; self.header.setText(f"<b>{self.command.number}</b>  •  {self.command.identification}  •  {self.command.phone or 'Sem telefone'}  •  {STATUS[self.command.status.value]}  •  {elapsed:.0f} min  •  Total: {brl(self.command.total)}"); self.table.setRowCount(len(self.command.items))
        for row,i in enumerate(self.command.items):
            for col,value in enumerate((i.code,i.product_name,i.package_type.value.title(),i.quantity,i.units_per_pack or 1,i.base_units,brl(i.price),brl(i.discount),brl(i.subtotal),i.username)):self.table.setItem(row,col,QTableWidgetItem(str(value)))
        editable=self.command.status in (CommandStatus.OPEN,CommandStatus.SERVING); self.product.setEnabled(editable); self.barcode.setEnabled(editable); self.package.setEnabled(editable); self.quantity.setEnabled(editable)
class CommandsView(QWidget):
    def __init__(self,session,service,catalog,customers,credit,parent=None):
        super().__init__(parent); self.session=session; self.service=service; self.catalog=catalog; self.customers=customers; self.credit=credit; self.rows=[]; self.active_rows=[]; root=QVBoxLayout(self); title=QLabel("Comandas"); title.setObjectName("pageTitle"); root.addWidget(title); tabs=QTabWidget(); command_page=QWidget(); command_layout=QVBoxLayout(command_page); command_layout.setContentsMargins(14,14,14,14); command_layout.setSpacing(14); self.slot_summary=QLabel(); self.slot_summary.setStyleSheet("QLabel { color:#ffbf00; font-size:15px; font-weight:700; padding:8px 4px; }"); command_layout.addWidget(self.slot_summary); self.slot_grid=QGridLayout(); self.slot_grid.setHorizontalSpacing(12); self.slot_grid.setVerticalSpacing(12); self.slot_buttons={}
        for slot in range(1,31):button=QPushButton(f"COMANDA {slot:02d}\nDisponível\n+ Abrir comanda"); button.setMinimumSize(180,96); button.setCursor(Qt.CursorShape.PointingHandCursor); button.clicked.connect(lambda checked=False,value=slot:self._slot_clicked(value)); self.slot_buttons[slot]=button; self.slot_grid.addWidget(button,(slot-1)//5,(slot-1)%5)
        command_layout.addLayout(self.slot_grid); legend=QLabel("● Aberta / em atendimento     ● Aguardando pagamento     ● Disponível"); legend.setStyleSheet("QLabel { color:#b9b9b9; padding:6px; font-size:12px; }"); command_layout.addWidget(legend); tabs.addTab(command_page,"Comandas")
        history_page=QWidget(); history_layout=QVBoxLayout(history_page); bar=QHBoxLayout(); self.search=QLineEdit(); self.search.setPlaceholderText("Número ou identificação"); self.status=QComboBox(); self.status.addItem("Finalizadas e canceladas",None); self.status.addItem("Finalizadas","finalizada"); self.status.addItem("Canceladas","cancelada"); display_button=QPushButton("Exibir comanda"); display_button.clicked.connect(self._display_history); refresh=QPushButton("Atualizar"); refresh.clicked.connect(self.refresh); print_button=QPushButton("Imprimir/PDF"); print_button.clicked.connect(self._print); bar.addWidget(self.search); bar.addWidget(self.status); bar.addWidget(display_button); bar.addWidget(refresh); bar.addWidget(print_button); history_layout.addLayout(bar); print_button.setVisible(Permission.TABS_PRINT in session.permissions); self.table=QTableWidget(0,8); self.table.setHorizontalHeaderLabels(["Número","Identificação","Abertura","Fechamento","Tempo","Itens","Total","Status"]); self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.table.cellDoubleClicked.connect(lambda *_:self._display_history()); history_layout.addWidget(self.table); tabs.addTab(history_page,"Histórico"); root.addWidget(tabs); self.timer=QTimer(self); self.timer.timeout.connect(self.refresh); self.timer.start(60000); self.refresh()
    def refresh(self):
        try:self.rows=self.service.list(self.session,search=self.search.text()); self.active_rows=[c for c in self.rows if c.status in (CommandStatus.OPEN,CommandStatus.SERVING,CommandStatus.AWAITING_PAYMENT)]
        except Exception as exc:QMessageBox.warning(self,"Comandas",str(exc)); return
        by_slot={c.slot_number:c for c in self.active_rows if c.slot_number}; now=datetime.now(timezone.utc)
        waiting=sum(c.status==CommandStatus.AWAITING_PAYMENT for c in self.active_rows); self.slot_summary.setText(f"30 posições  •  {len(self.active_rows)-waiting} em atendimento  •  {waiting} aguardando pagamento  •  {30-len(by_slot)} disponíveis")
        for slot,button in self.slot_buttons.items():
            command=by_slot.get(slot)
            if not command:
                button.setText(f"COMANDA {slot:02d}\nDisponível\n+ Abrir comanda"); button.setStyleSheet("QPushButton { text-align:left; padding:12px 16px; background:#242424; color:#f5f5f5; font-size:13px; font-weight:700; border:1px solid #555555; border-radius:12px; } QPushButton:hover { background:#302b20; border:2px solid #d99600; color:#ffbf00; } QPushButton:pressed { background:#171717; }")
            elif command.status==CommandStatus.AWAITING_PAYMENT:
                button.setText(f"COMANDA {slot:02d}  •  PAGAMENTO\n{command.identification}\n{len(command.items)} item(ns)  •  {brl(command.total)}"); button.setStyleSheet("QPushButton { text-align:left; padding:12px 16px; background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #7a4b00,stop:1 #3d2b0a); color:#ffffff; font-size:13px; font-weight:700; border:2px solid #ffb000; border-radius:12px; } QPushButton:hover { background:#8f5900; border-color:#ffd166; }")
            else:
                button.setText(f"COMANDA {slot:02d}  •  ABERTA\n{command.identification}\n{len(command.items)} item(ns)  •  {brl(command.total)}"); button.setStyleSheet("QPushButton { text-align:left; padding:12px 16px; background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #17633b,stop:1 #103c28); color:#ffffff; font-size:13px; font-weight:700; border:2px solid #35c878; border-radius:12px; } QPushButton:hover { background:#1c7548; border-color:#6ee7a5; }")
        history=[c for c in self.rows if c.status in (CommandStatus.FINALIZED,CommandStatus.CANCELLED) and (not self.status.currentData() or c.status.value==self.status.currentData())]; self.table.setRowCount(len(history)); self.history_rows=history
        for row,c in enumerate(history):
            elapsed=((c.closed_at or now)-c.opened_at).total_seconds()/60; values=(c.number,c.identification,c.opened_at.strftime("%d/%m/%Y %H:%M"),c.closed_at.strftime("%d/%m/%Y %H:%M") if c.closed_at else "—",f"{elapsed:.0f} min",len(c.items),brl(c.total),STATUS[c.status.value])
            for col,value in enumerate(values):self.table.setItem(row,col,QTableWidgetItem(str(value)))
    def _slot_clicked(self,slot):
        command=next((c for c in self.active_rows if c.slot_number==slot),None)
        if command:self._show_detail(command); return
        self._open(slot)
    def _open(self,slot=None):
        dialog=OpenCommandDialog(self.customers,self.session,self,slot)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        try:command=self.service.open(self.session,dialog.value())
        except ValueError as exc:
            if "já possui" in str(exc) and QMessageBox.question(self,"Comanda existente",f"{exc}\nDeseja abrir outra?")==QMessageBox.StandardButton.Yes:
                try:command=self.service.open(self.session,dialog.value(True))
                except Exception as inner:QMessageBox.warning(self,"Comanda",str(inner)); return
            else:QMessageBox.warning(self,"Comanda",str(exc)); return
        self.refresh(); self._show_detail(command)
    def _detail(self):
        row=self.table.currentRow()
        if row>=0:self._show_detail(self.rows[row])
    def _show_detail(self,command):CommandDetailDialog(self.session,self.service,self.catalog,self.customers,self.credit,command,self).exec(); self.refresh()
    def _close_selected(self):
        row=self.table.currentRow()
        if row<0:QMessageBox.information(self,"Fechar comanda","Selecione uma comanda."); return
        command=self.rows[row]
        if QMessageBox.question(self,"Fechar comanda",f"Enviar {command.number} ao PDV para pagamento?")!=QMessageBox.StandardButton.Yes:return
        try:self.service.request_close(self.session,command.id,command.version); QMessageBox.information(self,"Comanda enviada",f"{command.number} está disponível no PDV."); self.refresh()
        except Exception as exc:QMessageBox.warning(self,"Comanda não fechada",str(exc))
    def _cancel(self):
        row=self.table.currentRow()
        if row<0:return
        reason,ok=QInputDialog.getText(self,"Cancelar comanda","Motivo:")
        if ok and QMessageBox.question(self,"Confirmar cancelamento","Liberar as reservas e cancelar a comanda?")==QMessageBox.StandardButton.Yes:
            try:self.service.cancel(self.session,self.rows[row].id,self.rows[row].version,reason); self.refresh()
            except Exception as exc:QMessageBox.warning(self,"Cancelamento",str(exc))
    def _print(self):
        row=self.table.currentRow()
        if row<0:return
        command=self.history_rows[row]; path,_=QFileDialog.getSaveFileName(self,"Salvar conferência",f"comanda_{command.number}.pdf","PDF (*.pdf)")
        if path:
            try:self.service.export_pdf(self.session,command.id,path); QMessageBox.information(self,"Comanda","PDF salvo com sucesso.")
            except Exception as exc:QMessageBox.warning(self,"PDF",str(exc))
    def _display_history(self):
        row=self.table.currentRow()
        if row<0:QMessageBox.information(self,"Exibir comanda","Selecione uma comanda no histórico."); return
        self._show_detail(self.history_rows[row])
