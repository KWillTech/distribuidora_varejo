"""Central de relatórios e exportações."""
from datetime import date,timedelta
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QComboBox,QDateEdit,QFileDialog,QHBoxLayout,QLabel,QMessageBox,QPushButton,QTableWidget,QTableWidgetItem,QVBoxLayout,QWidget
from models.auth import Permission
from models.report import ReportFilter,ReportType
LABELS={ReportType.SALES:"Vendas",ReportType.STOCK:"Estoque atual",ReportType.PURCHASES:"Compras",ReportType.FINANCE:"Financeiro",ReportType.DELIVERIES:"Entregas",ReportType.CASH:"Fechamentos de caixa",ReportType.CREDIT:"Fiado e envelhecimento",ReportType.COMMANDS:"Comandas"}
class ReportsView(QWidget):
    def __init__(self,session,service,parent=None):
        super().__init__(parent); self.session=session; self.service=service; self.data=None; root=QVBoxLayout(self); title=QLabel("Relatórios"); title.setObjectName("pageTitle"); root.addWidget(title); filters=QHBoxLayout(); self.kind=QComboBox()
        for kind,label in LABELS.items():self.kind.addItem(label,kind)
        today=date.today(); self.start=QDateEdit(QDate(today.year,today.month,1)); self.end=QDateEdit(QDate.currentDate())
        for field in (self.start,self.end):field.setCalendarPopup(True); field.setDisplayFormat("dd/MM/yyyy")
        generate=QPushButton("Gerar relatório"); generate.clicked.connect(self.refresh); excel=QPushButton("Exportar Excel"); excel.clicked.connect(self._excel); pdf=QPushButton("Exportar PDF"); pdf.clicked.connect(self._pdf)
        for widget in (QLabel("Relatório"),self.kind,QLabel("De"),self.start,QLabel("Até"),self.end,generate,excel,pdf):filters.addWidget(widget)
        filters.addStretch(); root.addLayout(filters)
        if Permission.REPORTS_EXPORT not in session.permissions:excel.hide(); pdf.hide()
        self.total=QLabel("Gere um relatório para visualizar os dados."); self.total.setObjectName("metricValue"); root.addWidget(self.total); self.table=QTableWidget(); root.addWidget(self.table); self.refresh()
    def _filters(self):return ReportFilter(report_type=self.kind.currentData(),start_date=self.start.date().toPython(),end_date=self.end.date().toPython())
    def refresh(self):
        try:self.data=self.service.load(self.session,self._filters()); self.table.setColumnCount(len(self.data.columns)); self.table.setHorizontalHeaderLabels(self.data.columns); self.table.setRowCount(len(self.data.rows))
        except Exception as exc:QMessageBox.warning(self,"Relatório",str(exc)); return
        for row,values in enumerate(self.data.rows):
            for column,value in enumerate(values):self.table.setItem(row,column,QTableWidgetItem(value))
        self.table.resizeColumnsToContents(); self.total.setText(f"{self.data.total_label}: {self.data.total_value}")
    def _excel(self):
        if not self.data:return
        path,_=QFileDialog.getSaveFileName(self,"Salvar relatório Excel",f"relatorio_{self.kind.currentData().value}.xlsx","Excel (*.xlsx)")
        if path:
            try:self.service.export_excel(self.session,self.data,path); QMessageBox.information(self,"Relatório","Arquivo Excel salvo com sucesso.")
            except Exception as exc:QMessageBox.warning(self,"Exportação",str(exc))
    def _pdf(self):
        if not self.data:return
        path,_=QFileDialog.getSaveFileName(self,"Salvar relatório PDF",f"relatorio_{self.kind.currentData().value}.pdf","PDF (*.pdf)")
        if path:
            try:self.service.export_pdf(self.session,self.data,path); QMessageBox.information(self,"Relatório","Arquivo PDF salvo com sucesso.")
            except Exception as exc:QMessageBox.warning(self,"Exportação",str(exc))
