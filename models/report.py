"""Modelos da central de relatórios."""
from datetime import date
from enum import StrEnum
from pydantic import BaseModel
class ReportType(StrEnum): SALES="vendas"; STOCK="estoque"; PURCHASES="compras"; FINANCE="financeiro"; DELIVERIES="entregas"; CASH="caixas"; CREDIT="fiado"; COMMANDS="comandas"
class ReportFilter(BaseModel): report_type:ReportType; start_date:date; end_date:date
class ReportData(BaseModel): title:str; columns:list[str]; rows:list[list[str]]; total_label:str="Registros"; total_value:str="0"
