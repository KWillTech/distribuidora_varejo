"""Teste do formulário Qt de fornecedor."""

from dialogs.supplier_dialog import SupplierDialog


def test_supplier_dialog_returns_normalized_data(qtbot) -> None:
    dialog = SupplierDialog(); qtbot.addWidget(dialog)
    dialog.legal_name.setText("Fornecedor Teste Ltda")
    dialog.trade_name.setText("Fornecedor Teste")
    dialog.document.setText("04.252.011/0001-10")
    dialog.phone.setText("11999999999")
    data = dialog.data()
    assert data is not None
    assert data.document == "04252011000110"
    assert data.phone == "11999999999"

