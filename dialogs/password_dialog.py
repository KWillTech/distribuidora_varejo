"""Diálogo de alteração obrigatória de senha."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDialog, QFormLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout


class PasswordChangeDialog(QDialog):
    submitted = Signal(str, str)

    def __init__(self, mandatory: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Alterar senha")
        self.setModal(True)
        self.setMinimumWidth(420)
        self._mandatory = mandatory
        layout = QVBoxLayout(self)
        if mandatory:
            message = QLabel("Por segurança, altere a senha temporária antes de continuar.")
            message.setWordWrap(True)
            layout.addWidget(message)
        form = QFormLayout()
        self.current_password = QLineEdit()
        self.current_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.new_password = QLineEdit()
        self.new_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_password = QLineEdit()
        self.confirm_password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Senha atual", self.current_password)
        form.addRow("Nova senha", self.new_password)
        form.addRow("Confirmar senha", self.confirm_password)
        layout.addLayout(form)
        self.error_label = QLabel()
        self.error_label.setObjectName("errorLabel")
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)
        button = QPushButton("Salvar nova senha")
        button.clicked.connect(self._submit)
        layout.addWidget(button)

    def _submit(self) -> None:
        if self.new_password.text() != self.confirm_password.text():
            self.show_error("A confirmação da senha não confere.")
            return
        self.submitted.emit(self.current_password.text(), self.new_password.text())

    def show_error(self, message: str) -> None:
        self.error_label.setText(message)

    def reject(self) -> None:
        if not self._mandatory:
            super().reject()

