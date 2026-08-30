"""Exportações da central de relatórios."""
from models.report import ReportData
from services.reports import ReportService
class Audit:
    def record(self,**kwargs):pass
class User:username="admin"
class Session:user=User(); permissions=set()
def data():return ReportData(title="Relatório de teste",columns=["Produto","Quantidade","Total"],rows=[["Água","10","R$ 50,00"],["Cerveja","12","R$ 72,00"]],total_label="Faturamento",total_value="R$ 122,00")
def test_pdf_export(tmp_path):
    from models.auth import Permission
    session=Session(); session.permissions={Permission.REPORTS_EXPORT}; path=tmp_path/"report.pdf"; ReportService(None,Audit()).export_pdf(session,data(),path); assert path.read_bytes().startswith(b"%PDF")
def test_excel_export(tmp_path):
    from models.auth import Permission
    session=Session(); session.permissions={Permission.REPORTS_EXPORT}; path=tmp_path/"report.xlsx"; ReportService(None,Audit()).export_excel(session,data(),path); assert path.exists()
