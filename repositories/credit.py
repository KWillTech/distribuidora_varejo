"""Persistência atômica do limite, contas e movimentações de fiado."""
from calendar import monthrange
from datetime import date,datetime,time,timezone
from decimal import Decimal
from bson import ObjectId
from bson.decimal128 import Decimal128
from pymongo import ASCENDING,ReturnDocument
from models.auth import User,utc_now
from models.credit import CreditMovementType,Receivable,ReceivableStatus

def _id(v):return ObjectId(v) if ObjectId.is_valid(v) else v
def _dec(v):return v.to_decimal() if isinstance(v,Decimal128) else Decimal(str(v or 0))
def _add_months(value:date,months:int):
    month=value.month-1+months; year=value.year+month//12; month=month%12+1; return date(year,month,min(value.day,monthrange(year,month)[1]))
class CreditRepository:
    def __init__(self,database):self.customers=database["clientes"]; self.accounts=database["contas_receber"]; self.movements=database["movimentacoes_fiado"]; self.payments=database["pagamentos_fiado"]
    def customer_document(self,customer_id):return self.customers.find_one({"_id":_id(customer_id)})
    def has_overdue(self,customer_id):return self.accounts.count_documents({"cliente_id":customer_id,"origem":"fiado","saldo_aberto":{"$gt":Decimal128(Decimal("0"))},"vencimento":{"$lt":datetime.combine(datetime.now(timezone.utc).date(),time.min,tzinfo=timezone.utc)},"status":{"$in":[ReceivableStatus.PENDING.value,ReceivableStatus.PARTIAL.value,ReceivableStatus.OVERDUE.value]}})>0
    def reserve_credit(self,customer_id,amount,allow_over_limit=False):
        query={"_id":_id(customer_id),"ativo":True,"fiado_habilitado":True,"fiado_status":{"$nin":["bloqueado_manual","inativo"]}}
        if not allow_over_limit:query["$expr"]={"$lte":[{"$add":[{"$ifNull":["$fiado_saldo_devedor",Decimal128(Decimal("0"))]},Decimal128(amount)]},"$fiado_limite_credito"]}
        before=self.customers.find_one_and_update(query,{"$inc":{"fiado_saldo_devedor":Decimal128(amount)},"$set":{"fiado_status":"liberado","atualizado_em":utc_now()}},return_document=ReturnDocument.BEFORE)
        if not before:raise ValueError("Cliente não habilitado, bloqueado ou com limite de crédito insuficiente.")
        previous=_dec(before.get("fiado_saldo_devedor")); limit=_dec(before.get("fiado_limite_credito")); excess=max(Decimal("0"),previous+amount-limit)
        if excess:self.customers.update_one({"_id":_id(customer_id)},{"$set":{"fiado_excesso_limite":Decimal128(excess),"fiado_status":"limite_atingido"}})
        return previous,limit,excess
    def release_credit(self,customer_id,amount):
        self.customers.update_one({"_id":_id(customer_id)},{"$inc":{"fiado_saldo_devedor":Decimal128(-amount)},"$set":{"fiado_excesso_limite":Decimal128(Decimal("0")),"atualizado_em":utc_now()}})
    def create_account(self,sale,amount,due_date,user,authorization):
        due=datetime.combine(due_date,time.min,tzinfo=timezone.utc); now=utc_now(); doc={"origem":"fiado","venda_id":sale.id,"venda_numero":sale.number,"cliente_id":sale.customer_id,"cliente_nome":sale.customer_name,"valor_original":Decimal128(amount),"valor_pago":Decimal128(Decimal("0")),"saldo_aberto":Decimal128(amount),"data_venda":sale.created_at,"vencimento":due,"ultimo_pagamento":None,"status":ReceivableStatus.PENDING.value,"observacoes":sale.notes,"historico":[],"criado_em":now,"data_hora":now}
        result=self.accounts.insert_one(doc); doc["_id"]=result.inserted_id; self._movement(sale.customer_id,str(result.inserted_id),sale.id,CreditMovementType.SALE,amount,Decimal("0"),amount,user,reason=authorization.justification); return self._model(doc)
    def rollback_sale(self,sale_id,customer_id,amount):
        self.accounts.delete_one({"venda_id":sale_id,"origem":"fiado"}); self.movements.delete_many({"venda_id":sale_id,"tipo":CreditMovementType.SALE.value}); self.release_credit(customer_id,amount)
    def list_accounts(self,customer_id=None,status=None):
        query={"origem":"fiado"}
        if customer_id:query["cliente_id"]=customer_id
        if status:query["status"]=status
        docs=list(self.accounts.find(query).sort([("vencimento",ASCENDING),("data_venda",ASCENDING)])); return [self._model(d) for d in docs]
    def receive(self,customer_id,amount,method,user,cash_id=None,account_ids=None,notes=None):
        query={"origem":"fiado","cliente_id":customer_id,"status":{"$in":[ReceivableStatus.PENDING.value,ReceivableStatus.PARTIAL.value,ReceivableStatus.OVERDUE.value]},"saldo_aberto":{"$gt":Decimal128(Decimal("0"))}}
        if account_ids:query["_id"]={"$in":[_id(v) for v in account_ids]}
        accounts=list(self.accounts.find(query).sort([("vencimento",ASCENDING),("data_venda",ASCENDING)])); total=sum((_dec(d["saldo_aberto"]) for d in accounts),Decimal("0"))
        if not accounts:raise ValueError("Cliente não possui contas selecionadas em aberto.")
        if amount>total:raise ValueError("Pagamento não pode ser maior que o saldo selecionado.")
        remaining=amount; applied=[]; payment_id=str(ObjectId()); now=utc_now()
        try:
            for doc in accounts:
                if remaining<=0:break
                balance=_dec(doc["saldo_aberto"]); paid=min(balance,remaining); new_balance=balance-paid; status=ReceivableStatus.PAID.value if new_balance==0 else ReceivableStatus.PARTIAL.value
                updated=self.accounts.find_one_and_update({"_id":doc["_id"],"saldo_aberto":Decimal128(balance)},{"$inc":{"valor_pago":Decimal128(paid),"saldo_aberto":Decimal128(-paid)},"$set":{"status":status,"ultimo_pagamento":now},"$push":{"historico":{"tipo":"pagamento","valor":Decimal128(paid),"data_hora":now,"usuario":user.username}}},return_document=ReturnDocument.AFTER)
                if not updated:raise RuntimeError("Conta foi alterada por outro usuário. Atualize e tente novamente.")
                self._movement(customer_id,str(doc["_id"]),doc.get("venda_id"),CreditMovementType.PAYMENT,paid,balance,new_balance,user,method,cash_id,notes,payment_id); applied.append((doc,paid)); remaining-=paid
            self.customers.update_one({"_id":_id(customer_id),"fiado_saldo_devedor":{"$gte":Decimal128(amount)}},{"$inc":{"fiado_saldo_devedor":Decimal128(-amount)},"$set":{"atualizado_em":now}})
            self.payments.insert_one({"_id":ObjectId(payment_id),"cliente_id":customer_id,"valor":Decimal128(amount),"forma_pagamento":method,"contas":[{"conta_id":str(d["_id"]),"valor":Decimal128(v)} for d,v in applied],"caixa_id":cash_id,"usuario_id":user.id,"usuario":user.username,"observacao":notes,"data_hora":now,"estornado":False}); return payment_id,applied
        except Exception:
            for doc,paid in reversed(applied):self.accounts.update_one({"_id":doc["_id"]},{"$inc":{"valor_pago":Decimal128(-paid),"saldo_aberto":Decimal128(paid)},"$set":{"status":doc["status"],"ultimo_pagamento":doc.get("ultimo_pagamento")}})
            raise
    def movements_for_customer(self,customer_id):return list(self.movements.find({"cliente_id":customer_id}).sort("data_hora",1))
    def payments_list(self,customer_id=None):
        query={} if not customer_id else {"cliente_id":customer_id}; return list(self.payments.find(query).sort("data_hora",-1))
    def adjust(self,account_id,kind,amount,user,reason):
        account=self.accounts.find_one({"_id":_id(account_id),"origem":"fiado","status":{"$in":["pendente","parcialmente_pago","vencido"]}})
        if not account:raise ValueError("Conta não está aberta.")
        before=_dec(account["saldo_aberto"]); delta=-amount if kind==CreditMovementType.DISCOUNT else amount
        if before+delta<0:raise ValueError("Desconto supera o saldo da conta.")
        after=before+delta; status=ReceivableStatus.PAID.value if after==0 else account["status"]
        self.accounts.update_one({"_id":account["_id"],"saldo_aberto":Decimal128(before)},{"$inc":{"saldo_aberto":Decimal128(delta)},"$set":{"status":status},"$push":{"historico":{"tipo":kind.value,"valor":Decimal128(amount),"motivo":reason,"usuario":user.username,"data_hora":utc_now()}}}); self.customers.update_one({"_id":_id(account["cliente_id"])},{"$inc":{"fiado_saldo_devedor":Decimal128(delta)}}); self._movement(account["cliente_id"],str(account["_id"]),account.get("venda_id"),kind,amount,before,after,user,reason=reason); return self._model(self.accounts.find_one({"_id":account["_id"]}))
    def reverse_payment(self,payment_id,user,reason):
        payment=self.payments.find_one_and_update({"_id":_id(payment_id),"estornado":False},{"$set":{"estornado":True,"estornado_em":utc_now(),"motivo_estorno":reason,"estornado_por":user.username}},return_document=ReturnDocument.BEFORE)
        if not payment:raise ValueError("Pagamento não encontrado ou já estornado.")
        total=Decimal("0")
        for allocation in payment["contas"]:
            amount=_dec(allocation["valor"]); account=self.accounts.find_one({"_id":_id(allocation["conta_id"])}); before=_dec(account["saldo_aberto"]); after=before+amount; status=ReceivableStatus.PARTIAL.value if _dec(account["valor_pago"])-amount>0 else ReceivableStatus.PENDING.value; self.accounts.update_one({"_id":account["_id"]},{"$inc":{"valor_pago":Decimal128(-amount),"saldo_aberto":Decimal128(amount)},"$set":{"status":status}}); self._movement(account["cliente_id"],str(account["_id"]),account.get("venda_id"),CreditMovementType.REVERSAL,amount,before,after,user,reason=reason,origin_id=str(payment["_id"])); total+=amount
        self.customers.update_one({"_id":_id(payment["cliente_id"])},{"$inc":{"fiado_saldo_devedor":Decimal128(total)}}); return total,payment
    def cancel_account(self,account_id,user,reason):
        account=self.accounts.find_one_and_update({"_id":_id(account_id),"origem":"fiado","status":{"$nin":["cancelado","renegociado"]}},{"$set":{"status":ReceivableStatus.CANCELLED.value,"cancelado_em":utc_now(),"motivo_cancelamento":reason}},return_document=ReturnDocument.BEFORE)
        if not account:raise ValueError("Conta não pode ser cancelada.")
        balance=_dec(account["saldo_aberto"]); self.release_credit(account["cliente_id"],balance); self._movement(account["cliente_id"],str(account["_id"]),account.get("venda_id"),CreditMovementType.CANCELLATION,balance,balance,Decimal("0"),user,reason=reason); return self._model(self.accounts.find_one({"_id":account["_id"]}))
    def renegotiate(self,customer_id,account_ids,new_due,installments,interest,discount,user,reason):
        accounts=list(self.accounts.find({"_id":{"$in":[_id(v) for v in account_ids]},"cliente_id":customer_id,"status":{"$in":["pendente","parcialmente_pago","vencido"]}}));
        if len(accounts)!=len(account_ids):raise ValueError("Uma ou mais contas não podem ser renegociadas.")
        original=sum((_dec(a["saldo_aberto"]) for a in accounts),Decimal("0")); total=original+interest-discount
        if total<=0:raise ValueError("Total renegociado inválido.")
        group=str(ObjectId()); now=utc_now(); base=(total/installments).quantize(Decimal("0.01")); allocated=Decimal("0"); created=[]
        for account in accounts:self.accounts.update_one({"_id":account["_id"]},{"$set":{"status":ReceivableStatus.RENEGOTIATED.value,"renegociacao_id":group}})
        for index in range(installments):
            value=total-allocated if index==installments-1 else base; allocated+=value; due=_add_months(new_due,index); doc={"origem":"fiado","venda_id":f"reneg-{group}-{index+1}","venda_numero":f"RENEG-{group[-6:]}-{index+1}","cliente_id":customer_id,"cliente_nome":accounts[0].get("cliente_nome",""),"valor_original":Decimal128(value),"valor_pago":Decimal128(Decimal("0")),"saldo_aberto":Decimal128(value),"data_venda":now,"vencimento":datetime.combine(due,time.min,tzinfo=timezone.utc),"status":ReceivableStatus.PENDING.value,"renegociacao_id":group,"criado_em":now,"data_hora":now}; result=self.accounts.insert_one(doc); doc["_id"]=result.inserted_id; created.append(self._model(doc))
        delta=interest-discount
        if delta:self.customers.update_one({"_id":_id(customer_id)},{"$inc":{"fiado_saldo_devedor":Decimal128(delta)}})
        self._movement(customer_id,str(created[0].id),None,CreditMovementType.RENEGOTIATION,total,original,total,user,reason=reason); return created
    def summary(self):
        pipeline=[{"$match":{"origem":"fiado","status":{"$nin":["pago","cancelado","renegociado"]}}},{"$group":{"_id":None,"total":{"$sum":"$saldo_aberto"},"customers":{"$addToSet":"$cliente_id"}}}]; rows=list(self.accounts.aggregate(pipeline)); total=_dec(rows[0]["total"]) if rows else Decimal("0"); customers=len(rows[0]["customers"]) if rows else 0; today=datetime.combine(datetime.now(timezone.utc).date(),time.min,tzinfo=timezone.utc); month=today.replace(day=1); overdue=list(self.accounts.aggregate([{"$match":{"origem":"fiado","saldo_aberto":{"$gt":Decimal128(Decimal("0"))},"vencimento":{"$lt":today}}},{"$group":{"_id":None,"total":{"$sum":"$saldo_aberto"},"customers":{"$addToSet":"$cliente_id"}}}])); received_today=sum((_dec(p["valor"]) for p in self.payments.find({"data_hora":{"$gte":today},"estornado":False})),Decimal("0")); received_month=sum((_dec(p["valor"]) for p in self.payments.find({"data_hora":{"$gte":month},"estornado":False})),Decimal("0")); limits=list(self.customers.aggregate([{"$match":{"fiado_habilitado":True}},{"$group":{"_id":None,"granted":{"$sum":"$fiado_limite_credito"},"used":{"$sum":"$fiado_saldo_devedor"}}}])); return {"total":total,"overdue":_dec(overdue[0]["total"]) if overdue else Decimal("0"),"customers":customers,"delinquent":len(overdue[0]["customers"]) if overdue else 0,"received_today":received_today,"received_month":received_month,"limit_granted":_dec(limits[0]["granted"]) if limits else Decimal("0"),"limit_used":_dec(limits[0]["used"]) if limits else Decimal("0")}
    def _movement(self,customer_id,account_id,sale_id,kind,value,before,after,user,method=None,cash_id=None,reason=None,origin_id=None):self.movements.insert_one({"cliente_id":customer_id,"conta_receber_id":account_id,"venda_id":sale_id,"tipo":kind.value,"valor":Decimal128(value),"saldo_anterior":Decimal128(before),"saldo_posterior":Decimal128(after),"forma_pagamento":method,"caixa_id":cash_id,"usuario_id":user.id,"usuario":user.username,"motivo":reason,"data_hora":utc_now(),"movimentacao_origem_id":origin_id})
    @staticmethod
    def _model(d):
        due=d["vencimento"].date() if isinstance(d["vencimento"],datetime) else d["vencimento"]; status=d["status"]
        if status in (ReceivableStatus.PENDING.value,ReceivableStatus.PARTIAL.value) and due<datetime.now(timezone.utc).date():status=ReceivableStatus.OVERDUE.value
        return Receivable(id=str(d["_id"]),sale_id=d["venda_id"],sale_number=d.get("venda_numero",""),customer_id=d["cliente_id"],customer_name=d.get("cliente_nome",""),original_amount=_dec(d["valor_original"]),paid_amount=_dec(d.get("valor_pago")),open_balance=_dec(d["saldo_aberto"]),sale_date=d["data_venda"],due_date=due,last_payment_at=d.get("ultimo_pagamento"),status=status,notes=d.get("observacoes"),history=d.get("historico",[]))
