"""Testes da tela de login com pytest-qt."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit

from views.login_view import LoginView


def test_login_emits_credentials(qtbot) -> None:
    view = LoginView("Teste")
    qtbot.addWidget(view)
    view.login_input.setText("admin")
    view.password_input.setText("SenhaForte!123")

    with qtbot.waitSignal(view.login_requested, timeout=1000) as signal:
        qtbot.mouseClick(view.login_button, Qt.MouseButton.LeftButton)

    assert signal.args == ["admin", "SenhaForte!123"]


def test_show_password_changes_echo_mode(qtbot) -> None:
    view = LoginView("Teste")
    qtbot.addWidget(view)
    assert view.password_input.echoMode() == QLineEdit.EchoMode.Password
    view.show_password.setChecked(True)
    assert view.password_input.echoMode() == QLineEdit.EchoMode.Normal


def test_brand_logo_is_loaded(qtbot) -> None:
    view = LoginView("Adega do Bruninho")
    qtbot.addWidget(view)
    logo = view.findChild(type(view.error_label), "loginLogo")
    assert logo is not None
    assert logo.pixmap().isNull() is False


def test_login_uses_saved_theme(qtbot) -> None:
    view = LoginView("Adega do Bruninho"); qtbot.addWidget(view)
    view.apply_theme(False)
    assert "#loginCard { background: #ffffff" in view.styleSheet()
    view.apply_theme(True)
    assert "#loginCard { background: #171717" in view.styleSheet()


def test_loading_state_uses_same_login_window(qtbot) -> None:
    view = LoginView("Adega do Bruninho"); qtbot.addWidget(view)
    view.set_loading(True)
    assert view.loading_label.isHidden() is False
    assert view.login_button.isHidden()
    assert view.login_input.isEnabled() is False
    view.set_loading(False)
    assert view.loading_label.isHidden()
    assert view.login_button.isHidden() is False
