"""Persistência de contas, receitas, despesas e pagamentos."""
from calendar import monthrange
from datetime import date,datetime,time,timezone
from decimal import Decimal
from bson import ObjectId
from bson.decimal128 import Decimal128
from pymongo import ReturnDocument
from models.auth import utc_now
from models.finance import FinancialEntry,FinancialInput,FinancialKind,FinancialStatus,PaymentInput

def _id(value):return ObjectId(value) if ObjectId.is_valid(value) else value
def _dec(value):
    if value is None:return Decimal("0")
    return value.to_decimal() if isinstance(value,Decimal128) else Decimal(str(value))

class FinanceRepository:
    COLLECTIONS={FinancialKind.PAYABLE:"contas_pagar",FinancialKind.RECEIVABLE:"contas_receber",FinancialKind.EXPENSE:"despesas",FinancialKind.REVENUE:"receitas"}
    def __init__(self,database):self.database=database; self.payments=database["pagamentos_financeiros"]
    def create(self,data:FinancialInput):
        collection=self.database[self.COLLECTIONS[data.kind]]; recurring_id=str(ObjectId()) if data.recurring else None; first=None
        for index in range(data.recurrence_count):
            due=self._add_months(data.due_date,index); description=f"{data.description} ({index+1}/{data.recurrence_count})" if data.recurring else data.description; doc={"tipo":data.kind.value,"descricao":description,"categoria":data.category,"valor_original":Decimal128(data.amount),"valor":Decimal128(data.amount),"valor_pago":Decimal128(Decimal("0")),"vencimento":datetime.combine(due,time.min,tzinfo=timezone.utc),"status":FinancialStatus.OPEN.value,"observacoes":data.notes,"recorrente":data.recurring,"recorrencia_id":recurring_id,"numero_recorrencia":index+1,"total_recorrencias":data.recurrence_count,"criado_em":utc_now(),"data_hora":utc_now()}; result=collection.insert_one(doc); doc["_id"]=result.inserted_id
            if first is None:first=self._model(doc,data.kind)
        return first
    @staticmethod
    def _add_months(value:date,months:int)->date:
        month=value.month-1+months; year=value.year+month//12; month=month%12+1; return date(year,month,min(value.day,monthrange(year,month)[1]))
    def list(self,kind=None,status=None):
        kinds=[kind] if kind else list(self.COLLECTIONS); entries=[]
        for current in kinds:
            if current==FinancialKind.EXPENSE:
                query={"status":{"$ne":FinancialStatus.CANCELLED.value}} if status is None else ({"_id":{"$exists":False}} if status==FinancialStatus.CANCELLED else {"status":status.value})
            else:
                query={} if status is None else {"status":status.value}
            entries.extend(self._model(d,current) for d in self.database[self.COLLECTIONS[current]].find(query))
        return sorted(entries,key=lambda entry:(entry.due_date,entry.description))
    def pay(self,kind,entry_id,data:PaymentInput,user):
        collection=self.database[self.COLLECTIONS[kind]]; current=collection.find_one({"_id":_id(entry_id),"status":{"$in":[FinancialStatus.OPEN.value,FinancialStatus.PARTIAL.value]}})
        if not current:raise ValueError("Lançamento não está aberto para pagamento.")
        balance=_dec(current.get("valor_original",current.get("valor")))-_dec(current.get("valor_pago"))
        if data.amount>balance:raise ValueError("Pagamento supera o saldo do lançamento.")
        status=FinancialStatus.PAID if data.amount==balance else FinancialStatus.PARTIAL
        updated=collection.find_one_and_update({"_id":_id(entry_id),"status":{"$in":[FinancialStatus.OPEN.value,FinancialStatus.PARTIAL.value]}},{"$inc":{"valor_pago":Decimal128(data.amount)},"$set":{"status":status.value,"atualizado_em":utc_now()}},return_document=ReturnDocument.AFTER)
        self.payments.insert_one({"tipo":kind.value,"lancamento_id":entry_id,"valor":Decimal128(data.amount),"data_pagamento":datetime.combine(data.payment_date,time.min,tzinfo=timezone.utc),"forma_pagamento":data.payment_method,"observacoes":data.notes,"usuario":user.username,"data_hora":utc_now()}); return self._model(updated,kind)
    def update_expense(self,entry_id,data:FinancialInput):
        updated=self.database["despesas"].find_one_and_update({"_id":_id(entry_id),"status":FinancialStatus.OPEN.value,"valor_pago":Decimal128(Decimal("0"))},{"$set":{"descricao":data.description,"categoria":data.category,"valor_original":Decimal128(data.amount),"valor":Decimal128(data.amount),"vencimento":datetime.combine(data.due_date,time.min,tzinfo=timezone.utc),"observacoes":data.notes,"atualizado_em":utc_now()}},return_document=ReturnDocument.AFTER)
        if not updated:raise ValueError("Somente despesa aberta e sem pagamentos pode ser editada.")
        return self._model(updated,FinancialKind.EXPENSE)
    def cancel_expense(self,entry_id,reason):
        updated=self.database["despesas"].find_one_and_update({"_id":_id(entry_id),"status":FinancialStatus.OPEN.value,"valor_pago":Decimal128(Decimal("0"))},{"$set":{"status":FinancialStatus.CANCELLED.value,"motivo_cancelamento":reason,"cancelado_em":utc_now(),"atualizado_em":utc_now()}},return_document=ReturnDocument.AFTER)
        if not updated:raise ValueError("Somente despesa aberta e sem pagamentos pode ser excluída.")
        return self._model(updated,FinancialKind.EXPENSE)
    def cancel_expenses(self,entry_ids,reason):
        ids=[_id(value) for value in entry_ids]; result=self.database["despesas"].update_many({"_id":{"$in":ids},"status":FinancialStatus.OPEN.value,"valor_pago":Decimal128(Decimal("0"))},{"$set":{"status":FinancialStatus.CANCELLED.value,"motivo_cancelamento":reason,"cancelado_em":utc_now(),"atualizado_em":utc_now()}})
        return result.modified_count
    @staticmethod
    def _model(d,kind):
        due=d.get("vencimento") or d.get("data_hora") or utc_now(); return FinancialEntry(id=str(d["_id"]),kind=kind,description=d.get("descricao",kind.value),category=d.get("categoria","Outros"),original_amount=_dec(d.get("valor_original",d.get("valor"))),paid_amount=_dec(d.get("valor_pago")),due_date=due.date() if isinstance(due,datetime) else due,status=d.get("status",FinancialStatus.OPEN.value),notes=d.get("observacoes"),created_at=d.get("criado_em",d.get("data_hora",utc_now())))
