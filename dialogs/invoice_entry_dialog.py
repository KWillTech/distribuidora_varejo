"""Coleta obrigatória de validade dos produtos da NF-e."""
from datetime import date
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QDateEdit,QDialog,QDialogButtonBox,QFormLayout,QLabel,QVBoxLayout
from models.purchase import Purchase

class InvoiceExpiryDialog(QDialog):
    def __init__(self,purchase:Purchase,parent=None):
        super().__init__(parent); self.setWindowTitle("Validade dos produtos"); self.setMinimumWidth(520); root=QVBoxLayout(self); root.addWidget(QLabel(f"Pedido {purchase.number}\nInforme a validade de todos os produtos recebidos:")); form=QFormLayout(); self.fields={}
        for item in purchase.items:
            if item.product_id in self.fields: continue
            field=QDateEdit(); field.setCalendarPopup(True); field.setDisplayFormat("dd/MM/yyyy"); field.setMinimumDate(QDate.currentDate()); field.setDate(QDate.currentDate().addYears(1)); self.fields[item.product_id]=field; form.addRow(item.product_name,field)
        root.addLayout(form); buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel); buttons.button(QDialogButtonBox.StandardButton.Save).setText("Continuar"); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)
    def expiration_dates(self)->dict[str,date]: return {product_id:field.date().toPython() for product_id,field in self.fields.items()}
