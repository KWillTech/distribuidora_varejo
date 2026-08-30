"""Janela da Etapa 2 para administração de contas e sessão."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from dialogs.permissions_dialog import PermissionsDialog
from dialogs.user_dialog import UserDialog
from models.auth import AuthenticatedSession, Permission
from services.users import UserService


class UserManagementWindow(QWidget):
    def __init__(self, session: AuthenticatedSession, service: UserService, parent=None) -> None:
        super().__init__(parent)
        self.session = session
        self.service = service
        layout = QHBoxLayout(self)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Nome", "Usuário", "E-mail", "Perfil", "Status"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)
        actions = QVBoxLayout()
        self.new_button = QPushButton("Novo usuário")
        if Permission.USERS_CREATE not in session.permissions: self.new_button.hide()
        self.new_button.clicked.connect(self._create)
        self.toggle_button = QPushButton("Ativar/Inativar")
        if Permission.USERS_DEACTIVATE not in session.permissions: self.toggle_button.hide()
        self.toggle_button.clicked.connect(self._toggle_active)
        self.permissions_button = QPushButton("Permissões individuais")
        if Permission.PERMISSIONS_MANAGE not in session.permissions: self.permissions_button.hide()
        self.permissions_button.clicked.connect(self._permissions)
        self.reset_button = QPushButton("Redefinir senha")
        if Permission.USERS_RESET_PASSWORD not in session.permissions: self.reset_button.hide()
        self.reset_button.clicked.connect(self._reset_password)
        actions.addWidget(self.new_button)
        actions.addWidget(self.toggle_button)
        actions.addWidget(self.permissions_button)
        actions.addWidget(self.reset_button)
        actions.addStretch()
        layout.addLayout(actions)
        self.refresh()

    def refresh(self) -> None:
        try:
            users = self.service.list_users(self.session)
        except PermissionError:
            users = []
        self.table.setRowCount(len(users))
        for row, user in enumerate(users):
            values = (user.full_name, user.username, str(user.email), user.profile_code.value.title(), "Ativo" if user.active else "Inativo")
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, user)
                self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()

    def _create(self) -> None:
        dialog = UserDialog(self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        data = dialog.data()
        if data is None:
            return
        try:
            self.service.create_user(self.session, data)
            self.refresh()
        except (ValueError, RuntimeError, PermissionError) as exc:
            QMessageBox.warning(self, "Não foi possível cadastrar", str(exc))

    def _toggle_active(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Seleção", "Selecione um usuário.")
            return
        user = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        reason = "Alteração administrativa pela tela de usuários"
        try:
            self.service.set_active(self.session, user.id, not user.active, reason)
            self.refresh()
        except (ValueError, PermissionError) as exc:
            QMessageBox.warning(self, "Operação negada", str(exc))

    def _selected_user(self):
        row = self.table.currentRow()
        return None if row < 0 else self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)

    def _permissions(self) -> None:
        user = self._selected_user()
        if user is None:
            QMessageBox.information(self, "Seleção", "Selecione um usuário.")
            return
        dialog = PermissionsDialog(user, self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        try:
            self.service.update_permissions(self.session, user.id, *dialog.values())
            self.refresh()
        except (ValueError, PermissionError) as exc:
            QMessageBox.warning(self, "Operação negada", str(exc))

    def _reset_password(self) -> None:
        user = self._selected_user()
        if user is None:
            QMessageBox.information(self, "Seleção", "Selecione um usuário.")
            return
        password, accepted = QInputDialog.getText(self, "Senha temporária", "Nova senha temporária:", QLineEdit.EchoMode.Password)
        if not accepted:
            return
        try:
            self.service.reset_password(self.session, user.id, password)
            QMessageBox.information(self, "Senha redefinida", "O usuário deverá alterar a senha no próximo acesso.")
        except (ValueError, PermissionError) as exc:
            QMessageBox.warning(self, "Operação negada", str(exc))
