"""Diálogos de cadastro e endereços de clientes."""

from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QCheckBox, QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox, QPushButton, QSpinBox,QTabWidget, QTextEdit, QVBoxLayout, QWidget
from pydantic import ValidationError

from models.customer import Address, Customer, CustomerInput
from models.credit import CreditCustomerStatus,CreditProfile
from models.auth import Permission
from dialogs.catalog_dialogs import parse_money,money_text


class AddressDialog(QDialog):
    def __init__(self, address: Address | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Endereço")
        form = QFormLayout(self)
        self.label = QLineEdit(address.label if address else "Adicional")
        self.cep = QLineEdit(address.cep if address else ""); self.cep.setInputMask("00000-000;_")
        self.street = QLineEdit(address.street if address else "")
        self.number = QLineEdit(address.number if address else "")
        self.complement = QLineEdit(address.complement if address and address.complement else "")
        self.district = QLineEdit(address.district if address else "")
        self.city = QLineEdit(address.city if address else "")
        self.state = QLineEdit(address.state if address else ""); self.state.setMaxLength(2)
        self.reference = QLineEdit(address.reference if address and address.reference else "")
        for label, widget in (("Identificação", self.label), ("CEP", self.cep), ("Endereço", self.street), ("Número", self.number), ("Complemento", self.complement), ("Bairro", self.district), ("Cidade", self.city), ("UF", self.state), ("Referência", self.reference)):
            form.addRow(label, widget)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); form.addRow(buttons)

    def data(self) -> Address | None:
        try:
            return Address(label=self.label.text(), cep=self.cep.text(), street=self.street.text(), number=self.number.text(), complement=self.complement.text() or None, district=self.district.text(), city=self.city.text(), state=self.state.text(), reference=self.reference.text() or None)
        except ValidationError as exc:
            QMessageBox.warning(self, "Endereço inválido", exc.errors()[0]["msg"])
            return None

    def accept(self) -> None:
        if self.data() is not None:
            super().accept()


class CustomerDialog(QDialog):
    def __init__(self, customer: Customer | None = None, parent=None,session=None) -> None:
        super().__init__(parent)
        self.customer = customer
        self.additional_addresses = list(customer.additional_addresses) if customer else []
        self.setWindowTitle("Editar cliente" if customer else "Novo cliente")
        self.resize(700, 650)
        root = QVBoxLayout(self)
        tabs = QTabWidget(); root.addWidget(tabs)
        personal = QWidget(); form = QFormLayout(personal)
        self.full_name = QLineEdit(customer.full_name if customer and customer.full_name else "")
        self.cpf = QLineEdit(customer.cpf if customer and customer.cpf else ""); self.cpf.setInputMask("000.000.000-00;_")
        self.has_birth_date = QCheckBox("Informar data de nascimento")
        self.birth_date = QDateEdit(); self.birth_date.setCalendarPopup(True); self.birth_date.setDisplayFormat("dd/MM/yyyy"); self.birth_date.setMaximumDate(QDate.currentDate())
        if customer and customer.birth_date:
            self.has_birth_date.setChecked(True); self.birth_date.setDate(QDate(customer.birth_date.year, customer.birth_date.month, customer.birth_date.day))
        else:
            self.birth_date.setDate(QDate.currentDate().addYears(-18)); self.birth_date.setEnabled(False)
        self.has_birth_date.toggled.connect(self.birth_date.setEnabled)
        self.phone = QLineEdit(customer.phone if customer and customer.phone else ""); self.phone.setInputMask("(00) 00000-0000;_")
        self.whatsapp = QLineEdit(customer.whatsapp if customer and customer.whatsapp else ""); self.whatsapp.setInputMask("(00) 00000-0000;_")
        self.email = QLineEdit(customer.email if customer and customer.email else "")
        self.age_confirmed = QCheckBox("Maioridade confirmada para compra de bebidas alcoólicas")
        self.age_confirmed.setChecked(customer.age_confirmed if customer else False)
        self.status = QComboBox(); self.status.addItem("Ativo", True); self.status.addItem("Inativo", False); self.status.setCurrentIndex(0 if customer is None or customer.active else 1)
        self.notes = QTextEdit(customer.notes if customer and customer.notes else ""); self.notes.setMaximumHeight(100)
        for label, widget in (("Nome", self.full_name), ("CPF", self.cpf), ("", self.has_birth_date), ("Nascimento", self.birth_date), ("Celular", self.phone), ("WhatsApp", self.whatsapp), ("E-mail", self.email), ("Status", self.status), ("", self.age_confirmed), ("Observações", self.notes)):
            form.addRow(label, widget)
        tabs.addTab(personal, "Dados pessoais")
        address_page = QWidget(); address_layout = QVBoxLayout(address_page)
        self.main_group = QGroupBox("Endereço principal"); self.main_group.setCheckable(True); self.main_group.setChecked(bool(customer and customer.main_address))
        main_form = QFormLayout(self.main_group)
        address = customer.main_address if customer else None
        self.cep = QLineEdit(address.cep if address and address.cep else ""); self.cep.setInputMask("00000-000;_")
        self.street = QLineEdit(address.street if address else ""); self.number = QLineEdit(address.number if address else "")
        self.complement = QLineEdit(address.complement if address and address.complement else ""); self.district = QLineEdit(address.district if address else "")
        self.city = QLineEdit(address.city if address else ""); self.state = QLineEdit(address.state if address else ""); self.state.setMaxLength(2)
        self.reference = QLineEdit(address.reference if address and address.reference else "")
        for label, widget in (("CEP", self.cep), ("Endereço", self.street), ("Número", self.number), ("Complemento", self.complement), ("Bairro", self.district), ("Cidade", self.city), ("UF", self.state), ("Referência", self.reference)):
            main_form.addRow(label, widget)
        address_layout.addWidget(self.main_group)
        address_layout.addWidget(QLabel("Endereços adicionais"))
        self.address_list = QListWidget(); address_layout.addWidget(self.address_list)
        controls = QHBoxLayout(); add = QPushButton("Adicionar"); edit = QPushButton("Editar"); remove = QPushButton("Remover")
        add.clicked.connect(self._add_address); edit.clicked.connect(self._edit_address); remove.clicked.connect(self._remove_address)
        controls.addWidget(add); controls.addWidget(edit); controls.addWidget(remove); address_layout.addLayout(controls)
        tabs.addTab(address_page, "Endereços")
        credit_page=QWidget(); credit_form=QFormLayout(credit_page); profile=customer.credit if customer else CreditProfile(); self.credit_enabled=QCheckBox("Fiado habilitado"); self.credit_enabled.setChecked(profile.enabled); self.credit_limit=QLineEdit(money_text(profile.credit_limit)); self.credit_debt=QLineEdit(money_text(profile.debt_balance)); self.credit_debt.setReadOnly(True); self.credit_available=QLineEdit(money_text(profile.available_limit)); self.credit_available.setReadOnly(True); self.credit_due_day=QSpinBox(); self.credit_due_day.setRange(1,28); self.credit_due_day.setValue(profile.default_due_day or 1); self.credit_due_days=QSpinBox(); self.credit_due_days.setRange(1,365); self.credit_due_days.setValue(profile.due_days); self.credit_allow_overdue=QCheckBox("Permitir compra com conta vencida"); self.credit_allow_overdue.setChecked(profile.allow_overdue_purchase); self.credit_status=QLineEdit(profile.status.value.replace("_"," ").title()); self.credit_status.setReadOnly(True); self.credit_block_reason=QLineEdit(profile.block_reason or ""); self.credit_block_reason.setReadOnly(True); self.credit_notes=QTextEdit(profile.financial_notes or ""); self.credit_notes.setMaximumHeight(90)
        for label,widget in (("",self.credit_enabled),("Limite de crédito",self.credit_limit),("Saldo devedor",self.credit_debt),("Limite disponível",self.credit_available),("Dia padrão de vencimento",self.credit_due_day),("Dias para vencimento",self.credit_due_days),("",self.credit_allow_overdue),("Status",self.credit_status),("Motivo do bloqueio",self.credit_block_reason),("Observações financeiras",self.credit_notes)):credit_form.addRow(label,widget)
        can_manage=bool(session and Permission.CREDIT_ENABLE in session.permissions)
        for widget in (self.credit_enabled,self.credit_limit,self.credit_due_day,self.credit_due_days,self.credit_allow_overdue,self.credit_notes):widget.setEnabled(can_manage)
        tabs.addTab(credit_page,"Controle de Fiado")
        self._refresh_addresses()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)

    def _refresh_addresses(self) -> None:
        self.address_list.clear()
        for address in self.additional_addresses:
            self.address_list.addItem(f"{address.label}: {address.street}, {address.number} — {address.city}/{address.state}")

    def _add_address(self) -> None:
        dialog = AddressDialog(parent=self)
        if dialog.exec() == dialog.DialogCode.Accepted:
            value = dialog.data()
            if value: self.additional_addresses.append(value); self._refresh_addresses()

    def _edit_address(self) -> None:
        row = self.address_list.currentRow()
        if row < 0: return
        dialog = AddressDialog(self.additional_addresses[row], self)
        if dialog.exec() == dialog.DialogCode.Accepted:
            value = dialog.data()
            if value: self.additional_addresses[row] = value; self._refresh_addresses()

    def _remove_address(self) -> None:
        row = self.address_list.currentRow()
        if row >= 0: self.additional_addresses.pop(row); self._refresh_addresses()

    def data(self) -> CustomerInput | None:
        try:
            main_address = None
            if self.main_group.isChecked():
                main_address = Address(label="Principal", cep=self.cep.text(), street=self.street.text(), number=self.number.text(), complement=self.complement.text() or None, district=self.district.text(), city=self.city.text(), state=self.state.text(), reference=self.reference.text() or None)
            return CustomerInput(
                full_name=self.full_name.text() or None, cpf=self.cpf.text() or None,
                birth_date=self.birth_date.date().toPython() if self.has_birth_date.isChecked() else None,
                phone=self.phone.text(), whatsapp=self.whatsapp.text() or None, email=self.email.text() or None,
                main_address=main_address, additional_addresses=self.additional_addresses,
                notes=self.notes.toPlainText() or None, age_confirmed=self.age_confirmed.isChecked(), active=bool(self.status.currentData()),credit=CreditProfile(enabled=self.credit_enabled.isChecked(),credit_limit=parse_money(self.credit_limit.text()) or Decimal("0"),debt_balance=self.customer.credit.debt_balance if self.customer else Decimal("0"),default_due_day=self.credit_due_day.value(),due_days=self.credit_due_days.value(),allow_overdue_purchase=self.credit_allow_overdue.isChecked(),status=self.customer.credit.status if self.customer else (CreditCustomerStatus.RELEASED if self.credit_enabled.isChecked() else CreditCustomerStatus.INACTIVE),block_reason=self.customer.credit.block_reason if self.customer else None,blocked_at=self.customer.credit.blocked_at if self.customer else None,blocked_by=self.customer.credit.blocked_by if self.customer else None,financial_notes=self.credit_notes.toPlainText() or None),
            )
        except ValidationError as exc:
            QMessageBox.warning(self, "Dados inválidos", exc.errors()[0]["msg"])
            return None

    def accept(self) -> None:
        if self.data() is not None:
            super().accept()
