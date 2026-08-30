"""Persistência atômica de caixas e suas movimentações."""
from decimal import Decimal
from bson import ObjectId
from bson.decimal128 import Decimal128
from pymongo import ReturnDocument
from pymongo.database import Database
from models.auth import User,utc_now
from models.cash import CashCloseInput,CashMovementInput,CashMovementType,CashRegister,CashStatus

def _id(v): return ObjectId(v) if ObjectId.is_valid(v) else v
def _dec(v): return v.to_decimal() if isinstance(v,Decimal128) else Decimal(str(v or 0))
class CashRepository:
    def __init__(self,database:Database): self.cash=database["caixas"]; self.movements=database["movimentacoes_caixa"]
    def get_open(self,user_id:str)->CashRegister|None:
        row=self.cash.find_one({"usuario_id":user_id,"status":CashStatus.OPEN.value}); return self._model(row) if row else None
    def open(self,user:User,amount:Decimal)->CashRegister:
        if self.get_open(user.id or user.username): raise ValueError("Usuário já possui caixa aberto.")
        now=utc_now(); doc={"usuario_id":user.id or user.username,"usuario":user.username,"valor_inicial":Decimal128(amount),"saldo_esperado":Decimal128(amount),"status":CashStatus.OPEN.value,"aberto_em":now,"fechado_em":None}; result=self.cash.insert_one(doc); doc["_id"]=result.inserted_id
        if amount: self._movement(str(result.inserted_id),user,CashMovementInput(movement_type=CashMovementType.OPENING,amount=amount,reason="Abertura de caixa"),amount)
        return self._model(doc)
    def add_movement(self,cash_id:str,user:User,data:CashMovementInput)->CashRegister:
        delta=-data.amount if data.movement_type in (CashMovementType.WITHDRAWAL,CashMovementType.REVERSAL) else data.amount
        minimum = Decimal128(-delta) if delta < 0 else Decimal128(Decimal("0"))
        before=self.cash.find_one_and_update({"_id":_id(cash_id),"status":CashStatus.OPEN.value,"saldo_esperado":{"$gte":minimum}},{"$inc":{"saldo_esperado":Decimal128(delta)}},return_document=ReturnDocument.BEFORE)
        if not before: raise ValueError("Caixa fechado ou saldo insuficiente.")
        self._movement(cash_id,user,data,_dec(before["saldo_esperado"])+delta); row=self.cash.find_one({"_id":_id(cash_id)}); return self._model(row)
    def _movement(self,cash_id,user,data,balance):
        self.movements.insert_one({"caixa_id":cash_id,"tipo":data.movement_type.value,"valor":Decimal128(data.amount),"forma_pagamento":data.payment_method,"motivo":data.reason,"documento_relacionado":data.related_document,"saldo_apos":Decimal128(balance),"usuario_id":user.id or user.username,"usuario":user.username,"data_hora":utc_now()})
    def close(self,cash_id:str,data:CashCloseInput)->CashRegister:
        current=self.cash.find_one({"_id":_id(cash_id),"status":CashStatus.OPEN.value})
        if not current: raise ValueError("Caixa não está aberto.")
        expected=_dec(current["saldo_esperado"]); difference=data.counted_amount-expected
        if difference and not (data.justification or "").strip(): raise ValueError("Informe a justificativa da diferença.")
        row=self.cash.find_one_and_update({"_id":_id(cash_id),"status":CashStatus.OPEN.value},{"$set":{"status":CashStatus.CLOSED.value,"valor_contado":Decimal128(data.counted_amount),"diferenca":Decimal128(difference),"justificativa":data.justification,"fechado_em":utc_now()}},return_document=ReturnDocument.AFTER); return self._model(row)
    def history(self,limit=100): return [self._model(x) for x in self.cash.find().sort("aberto_em",-1).limit(limit)]
    @staticmethod
    def _model(d): return CashRegister(id=str(d["_id"]),user_id=d["usuario_id"],username=d["usuario"],opening_amount=_dec(d["valor_inicial"]),expected_amount=_dec(d["saldo_esperado"]),counted_amount=_dec(d["valor_contado"]) if d.get("valor_contado") is not None else None,difference=_dec(d["diferenca"]) if d.get("diferenca") is not None else None,justification=d.get("justificativa"),status=d["status"],opened_at=d["aberto_em"],closed_at=d.get("fechado_em"))
