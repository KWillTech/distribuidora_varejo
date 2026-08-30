"""Tela centralizada de login."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtWidgets import QCheckBox, QFrame, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from utils.resources import logo_pixmap


class LoginView(QWidget):
    login_requested = Signal(str, str)

    def __init__(self, app_name: str) -> None:
        super().__init__()
        self.apply_saved_theme()
        self.setWindowTitle(app_name)
        self.resize(900, 600)
        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card = QFrame()
        card.setObjectName("loginCard")
        card.setFixedWidth(430)
        layout = QVBoxLayout(card)
        logo = QLabel()
        logo.setObjectName("loginLogo")
        logo.setPixmap(logo_pixmap(270, 230))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title = QLabel("Adega do Bruninho")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle = QLabel("Acesse sua conta")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.login_input = QLineEdit()
        self.login_input.setPlaceholderText("Usuário ou e-mail")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Senha")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.show_password = QCheckBox("Mostrar senha")
        self.show_password.toggled.connect(self._toggle_password)
        self.error_label = QLabel()
        self.error_label.setObjectName("errorLabel")
        self.error_label.setWordWrap(True)
        self.loading_label = QLabel("Carregando sistema…")
        self.loading_label.setObjectName("loadingLabel")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.hide()
        self.login_button = QPushButton("Entrar")
        self.login_button.setObjectName("primaryButton")
        self.login_button.clicked.connect(self._submit)
        self.password_input.returnPressed.connect(self._submit)
        for widget in (logo, title, subtitle, self.login_input, self.password_input, self.show_password, self.error_label, self.loading_label, self.login_button):
            layout.addWidget(widget)
        root.addWidget(card)

    def apply_saved_theme(self) -> None:
        """Aplica ao login a última preferência de tema do usuário."""
        settings = QSettings("DistribuidoraVarejo", "DistribuidoraVarejo"); settings.sync()
        dark = settings.value("dark_theme", False, type=bool)
        self.apply_theme(dark)

    def apply_theme(self, dark: bool) -> None:
        """Aplica explicitamente um tema, facilitando sincronização e testes."""
        style_name = "dark.qss" if dark else "app.qss"
        stylesheet = Path(__file__).resolve().parent.parent / "resources" / "styles" / style_name
        self.setStyleSheet(stylesheet.read_text(encoding="utf-8"))

    def _toggle_password(self, visible: bool) -> None:
        self.password_input.setEchoMode(QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password)

    def set_loading(self, loading: bool) -> None:
        self.loading_label.setVisible(loading)
        self.login_button.setVisible(not loading)
        self.login_input.setEnabled(not loading); self.password_input.setEnabled(not loading); self.show_password.setEnabled(not loading)

    def _submit(self) -> None:
        if not self.login_input.text().strip() or not self.password_input.text():
            self.show_error("Informe o usuário e a senha.")
            return
        self.login_button.setEnabled(False)
        self.error_label.clear()
        self.login_requested.emit(self.login_input.text(), self.password_input.text())

    def show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.password_input.clear()
        self.login_button.setEnabled(True)
        self.password_input.setFocus()
