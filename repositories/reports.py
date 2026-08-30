"""Consultas somente leitura para relatórios."""
from datetime import datetime,time,timedelta,timezone
from decimal import Decimal
from bson.decimal128 import Decimal128
from models.report import ReportData,ReportFilter,ReportType
def _dec(v):return v.to_decimal() if isinstance(v,Decimal128) else Decimal(str(v or 0))
def _brl(v):return f"R$ {_dec(v):,.2f}".replace(",","X").replace(".",",").replace("X",".")
def _date(v):return v.strftime("%d/%m/%Y %H:%M") if isinstance(v,datetime) else "-"
class ReportRepository:
    def __init__(self,database):self.db=database
    def load(self,f:ReportFilter):
        start=datetime.combine(f.start_date,time.min,tzinfo=timezone.utc); end=datetime.combine(f.end_date+timedelta(days=1),time.min,tzinfo=timezone.utc)
        if f.report_type==ReportType.SALES:return self._sales(start,end)
        if f.report_type==ReportType.STOCK:return self._stock()
        if f.report_type==ReportType.PURCHASES:return self._purchases(start,end)
        if f.report_type==ReportType.FINANCE:return self._finance(start,end)
        if f.report_type==ReportType.DELIVERIES:return self._deliveries(start,end)
        if f.report_type==ReportType.CREDIT:return self._credit(start,end)
        if f.report_type==ReportType.COMMANDS:return self._commands(start,end)
        return self._cash(start,end)
    def _sales(self,start,end):
        docs=list(self.db["vendas"].find({"data_hora":{"$gte":start,"$lt":end},"status":"concluida"}).sort("data_hora",-1)); rows=[[d.get("numero",""),_date(d.get("data_hora")),d.get("cliente_nome") or "Balcão",d.get("usuario",""),_brl(d.get("total")),d.get("status","").title()] for d in docs]; return ReportData(title="Vendas por período",columns=["Venda","Data","Cliente","Usuário","Total","Status"],rows=rows,total_label="Faturamento",total_value=_brl(sum((_dec(d.get("total")) for d in docs),Decimal("0"))))
    def _stock(self):
        docs=list(self.db["produtos"].find({"ativo":True}).sort("nome",1)); rows=[[d.get("nome",""),d.get("categoria_nome",""),str(d.get("estoque_atual_unidades",0)),str(d.get("estoque_minimo",0)),"Baixo" if d.get("estoque_atual_unidades",0)<=d.get("estoque_minimo",0) else "Normal"] for d in docs]; return ReportData(title="Estoque atual",columns=["Produto","Categoria","Estoque","Mínimo","Situação"],rows=rows,total_value=str(len(rows)))
    def _purchases(self,start,end):
        docs=list(self.db["compras"].find({"data_hora":{"$gte":start,"$lt":end}}).sort("data_hora",-1)); rows=[[d.get("numero",""),_date(d.get("data_hora")),d.get("fornecedor_nome",""),_brl(d.get("total")),d.get("status","").replace("_"," ").title()] for d in docs]; return ReportData(title="Compras por fornecedor",columns=["Pedido","Data","Fornecedor","Total","Status"],rows=rows,total_label="Total comprado",total_value=_brl(sum((_dec(d.get("total")) for d in docs),Decimal("0"))))
    def _finance(self,start,end):
        rows=[]; total=Decimal("0")
        for collection,label in (("contas_pagar","Conta a pagar"),("contas_receber","Conta a receber"),("despesas","Despesa"),("receitas","Receita")):
            for d in self.db[collection].find({"data_hora":{"$gte":start,"$lt":end},"status":{"$ne":"cancelada"}}):
                value=_dec(d.get("valor_original",d.get("valor"))); total+=value; rows.append([label,d.get("descricao",""),d.get("categoria","Outros"),_date(d.get("vencimento")),_brl(value),d.get("status","").title()])
        return ReportData(title="Movimentação financeira",columns=["Tipo","Descrição","Categoria","Vencimento","Valor","Status"],rows=rows,total_label="Valor dos lançamentos",total_value=_brl(total))
    def _deliveries(self,start,end):
        docs=list(self.db["entregas"].find({"criado_em":{"$gte":start,"$lt":end}}).sort("criado_em",-1)); rows=[[d.get("numero",""),d.get("cliente_nome",""),d.get("entregador_nome") or "Não atribuído",str(d.get("volumes",0)),d.get("status","").replace("_"," ").title(),_date(d.get("criado_em"))] for d in docs]; return ReportData(title="Entregas",columns=["Pedido","Cliente","Entregador","Volumes","Status","Data"],rows=rows,total_value=str(len(rows)))
    def _cash(self,start,end):
        docs=list(self.db["caixas"].find({"aberto_em":{"$gte":start,"$lt":end}}).sort("aberto_em",-1)); rows=[[d.get("usuario",""),_date(d.get("aberto_em")),_date(d.get("fechado_em")),_brl(d.get("saldo_esperado")),_brl(d.get("valor_contado")),_brl(d.get("diferenca")),d.get("status","").title()] for d in docs]; return ReportData(title="Fechamentos de caixa",columns=["Usuário","Abertura","Fechamento","Esperado","Contado","Diferença","Status"],rows=rows,total_value=str(len(rows)))
    def _credit(self,start,end):
        today=datetime.now(timezone.utc); docs=list(self.db["contas_receber"].find({"origem":"fiado","data_venda":{"$gte":start,"$lt":end}}).sort("vencimento",1)); rows=[]; total=Decimal("0")
        for d in docs:
            balance=_dec(d.get("saldo_aberto")); total+=balance; due=d.get("vencimento"); days=max(0,(today.date()-due.date()).days) if isinstance(due,datetime) else 0
            bucket="A vencer" if not isinstance(due,datetime) or due.date()>=today.date() else "1–7 dias" if days<=7 else "8–15 dias" if days<=15 else "16–30 dias" if days<=30 else "31–60 dias" if days<=60 else "Mais de 60 dias"
            rows.append([d.get("cliente_nome",""),d.get("venda_numero",""),_date(d.get("data_venda")),_date(due),_brl(d.get("valor_original")),_brl(d.get("valor_pago")),_brl(balance),bucket,d.get("status","").replace("_"," ").title()])
        return ReportData(title="Fiado e envelhecimento da dívida",columns=["Cliente","Venda","Compra","Vencimento","Original","Pago","Saldo","Faixa de atraso","Status"],rows=rows,total_label="Saldo em aberto",total_value=_brl(total))
    def _commands(self,start,end):
        docs=list(self.db["comandas"].find({"data_abertura":{"$gte":start,"$lt":end}}).sort("data_abertura",-1)); rows=[]; total=Decimal("0")
        for d in docs:
            value=_dec(d.get("total")); total+=value; closed=d.get("data_fechamento"); minutes=int(((closed or datetime.now(timezone.utc))-d["data_abertura"]).total_seconds()//60); items=d.get("itens",[]); unit=sum(x.get("quantidade",0) for x in items if x.get("tipo_venda")=="unidade"); packs=sum(x.get("quantidade",0) for x in items if x.get("tipo_venda")=="fardo")
            rows.append([d.get("numero",""),d.get("identificacao") or (d.get("cliente_snapshot") or {}).get("nome","") ,_date(d.get("data_abertura")),d.get("usuario_responsavel",""),d.get("tipo_atendimento","").title(),str(unit),str(packs),str(minutes),_brl(value),d.get("status","").replace("_"," ").title()])
        return ReportData(title="Comandas por período",columns=["Comanda","Cliente/identificação","Abertura","Usuário","Atendimento","Unidades","Fardos","Tempo (min)","Total","Status"],rows=rows,total_label="Valor das comandas",total_value=_brl(total))
