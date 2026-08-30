"""Formulário completo de fornecedores."""

from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QTextEdit, QVBoxLayout
from pydantic import ValidationError

from dialogs.customer_dialog import AddressDialog
from models.customer import Address
from models.supplier import Supplier, SupplierInput


class SupplierDialog(QDialog):
    def __init__(self, supplier: Supplier | None = None, parent=None) -> None:
        super().__init__(parent); self.supplier = supplier; self.address: Address | None = supplier.address if supplier else None
        self.setWindowTitle("Editar fornecedor" if supplier else "Novo fornecedor"); self.resize(620, 650)
        root = QVBoxLayout(self); form = QFormLayout()
        self.legal_name = QLineEdit(supplier.legal_name if supplier else "")
        self.trade_name = QLineEdit(supplier.trade_name if supplier and supplier.trade_name else "")
        self.document = QLineEdit(supplier.document if supplier else ""); self.document.setPlaceholderText("CPF ou CNPJ")
        self.state_registration = QLineEdit(supplier.state_registration if supplier and supplier.state_registration else "")
        self.phone = QLineEdit(supplier.phone if supplier and supplier.phone else ""); self.phone.setInputMask("(00) 00000-0000;_")
        self.whatsapp = QLineEdit(supplier.whatsapp if supplier and supplier.whatsapp else ""); self.whatsapp.setInputMask("(00) 00000-0000;_")
        self.email = QLineEdit(supplier.email if supplier and supplier.email else "")
        self.commercial_contact = QLineEdit(supplier.commercial_contact if supplier and supplier.commercial_contact else "")
        self.delivery_term = QLineEdit(supplier.delivery_term if supplier and supplier.delivery_term else "")
        self.payment_terms = QLineEdit(supplier.payment_terms if supplier and supplier.payment_terms else "")
        self.status = QComboBox(); self.status.addItem("Ativo", True); self.status.addItem("Inativo", False); self.status.setCurrentIndex(0 if supplier is None or supplier.active else 1)
        self.notes = QTextEdit(supplier.notes if supplier and supplier.notes else ""); self.notes.setMaximumHeight(90)
        for label, widget in (("Razão social *", self.legal_name), ("Nome fantasia", self.trade_name), ("CPF/CNPJ *", self.document), ("Inscrição estadual", self.state_registration), ("Telefone", self.phone), ("WhatsApp", self.whatsapp), ("E-mail", self.email), ("Contato comercial", self.commercial_contact), ("Prazo de entrega", self.delivery_term), ("Condição de pagamento", self.payment_terms), ("Status", self.status), ("Observações", self.notes)): form.addRow(label, widget)
        root.addLayout(form)
        address_row = QHBoxLayout(); self.address_label = QLabel(); address_button = QPushButton("Definir endereço"); address_button.clicked.connect(self._address); address_row.addWidget(self.address_label, 1); address_row.addWidget(address_button); root.addLayout(address_row); self._refresh_address()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)

    def _address(self) -> None:
        dialog = AddressDialog(self.address, self)
        if dialog.exec() == dialog.DialogCode.Accepted:
            self.address = dialog.data(); self._refresh_address()

    def _refresh_address(self) -> None:
        self.address_label.setText(f"Endereço: {self.address.street}, {self.address.number} — {self.address.city}/{self.address.state}" if self.address else "Endereço não informado")

    def data(self) -> SupplierInput | None:
        try:
            return SupplierInput(legal_name=self.legal_name.text(), trade_name=self.trade_name.text() or None, document=self.document.text(), state_registration=self.state_registration.text() or None, phone=self.phone.text() or None, whatsapp=self.whatsapp.text() or None, email=self.email.text() or None, address=self.address, commercial_contact=self.commercial_contact.text() or None, delivery_term=self.delivery_term.text() or None, payment_terms=self.payment_terms.text() or None, notes=self.notes.toPlainText() or None, active=bool(self.status.currentData()))
        except ValidationError as exc:
            QMessageBox.warning(self, "Dados inválidos", exc.errors()[0]["msg"]); return None

    def accept(self) -> None:
        if self.data() is not None: super().accept()

