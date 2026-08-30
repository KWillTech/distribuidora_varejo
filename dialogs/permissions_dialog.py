"""Edição de exceções individuais às permissões do perfil."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout
from PySide6.QtCore import Qt

from models.auth import Permission, User


class PermissionsDialog(QDialog):
    def __init__(self, user: User, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Permissões individuais — {user.username}")
        self.resize(650, 600)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Marque Liberação ou Bloqueio. Sem marca usa a regra do perfil."))
        self.table = QTableWidget(len(Permission), 3)
        self.table.setHorizontalHeaderLabels(["Permissão", "Liberar", "Bloquear"])
        for row, permission in enumerate(Permission):
            name = QTableWidgetItem(permission.value)
            name.setFlags(name.flags() & ~Qt.ItemFlag.ItemIsEditable)
            grant = QTableWidgetItem()
            grant.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            grant.setCheckState(Qt.CheckState.Checked if permission in user.individual_grants else Qt.CheckState.Unchecked)
            denial = QTableWidgetItem()
            denial.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            denial.setCheckState(Qt.CheckState.Checked if permission in user.individual_denials else Qt.CheckState.Unchecked)
            self.table.setItem(row, 0, name)
            self.table.setItem(row, 1, grant)
            self.table.setItem(row, 2, denial)
        self.table.cellChanged.connect(self._exclusive_checks)
        self.table.resizeColumnsToContents()
        layout.addWidget(self.table)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _exclusive_checks(self, row: int, column: int) -> None:
        if column not in (1, 2) or self.table.item(row, column).checkState() != Qt.CheckState.Checked:
            return
        other = 2 if column == 1 else 1
        self.table.blockSignals(True)
        self.table.item(row, other).setCheckState(Qt.CheckState.Unchecked)
        self.table.blockSignals(False)

    def values(self) -> tuple[set[Permission], set[Permission]]:
        grants: set[Permission] = set()
        denials: set[Permission] = set()
        for row, permission in enumerate(Permission):
            if self.table.item(row, 1).checkState() == Qt.CheckState.Checked:
                grants.add(permission)
            if self.table.item(row, 2).checkState() == Qt.CheckState.Checked:
                denials.add(permission)
        return grants, denials

