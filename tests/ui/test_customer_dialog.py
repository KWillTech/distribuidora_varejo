"""Testes do formulário Qt de clientes."""

from dialogs.customer_dialog import CustomerDialog


def test_customer_dialog_builds_normalized_input(qtbot) -> None:
    dialog = CustomerDialog()
    qtbot.addWidget(dialog)
    dialog.full_name.setText("Cliente da Adega")
    dialog.cpf.setText("52998224725")
    dialog.phone.setText("11999999999")
    dialog.whatsapp.setText("11988888888")
    dialog.email.setText("CLIENTE@EXAMPLE.COM")

    data = dialog.data()

    assert data is not None
    assert data.cpf == "52998224725"
    assert data.phone == "11999999999"
    assert data.email == "cliente@example.com"


def test_optional_identification_and_inactive_status(qtbot) -> None:
    dialog = CustomerDialog()
    qtbot.addWidget(dialog)
    dialog.status.setCurrentIndex(1)

    data = dialog.data()

    assert data is not None
    assert data.full_name is None
    assert data.cpf is None
    assert data.phone is None
    assert data.active is False
