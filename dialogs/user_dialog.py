"""Formulário administrativo para criação de usuários."""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QMessageBox
from pydantic import ValidationError

from models.auth import ProfileCode, UserCreate


class UserDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Novo usuário")
        self.setMinimumWidth(440)
        layout = QFormLayout(self)
        self.full_name = QLineEdit()
        self.username = QLineEdit()
        self.email = QLineEdit()
        self.profile = QComboBox()
        for code in ProfileCode:
            self.profile.addItem(code.value.replace("_", " ").title(), code)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("Mín. 10 caracteres, maiúscula, número e símbolo")
        layout.addRow("Nome completo", self.full_name)
        layout.addRow("Usuário", self.username)
        layout.addRow("E-mail", self.email)
        layout.addRow("Perfil", self.profile)
        layout.addRow("Senha temporária", self.password)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def data(self) -> UserCreate | None:
        try:
            return UserCreate(
                full_name=self.full_name.text(), username=self.username.text(), email=self.email.text(),
                profile_code=self.profile.currentData(), temporary_password=self.password.text(),
            )
        except ValidationError as exc:
            QMessageBox.warning(self, "Dados inválidos", exc.errors()[0]["msg"])
            return None

    def accept(self) -> None:
        if self.data() is not None:
            super().accept()

