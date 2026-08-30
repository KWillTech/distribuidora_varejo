"""Persistência de vendas e pagamentos do PDV."""
from decimal import Decimal
from bson.decimal128 import Decimal128
from pymongo import ReturnDocument
from pymongo.database import Database
from models.auth import User, utc_now
from models.sale import Sale, SaleInput, SaleItem, SalePayment, SaleStatus

def _dec(value): return value.to_decimal() if isinstance(value, Decimal128) else Decimal(str(value or 0))

class SaleRepository:
    def __init__(self, database: Database): self.sales = database["vendas"]; self.settings = database["configuracoes"]
    def _number(self):
        row = self.settings.find_one_and_update({"chave":"sequencia_venda"},{"$inc":{"valor":1}},upsert=True,return_document=ReturnDocument.AFTER); return f"VD-{int(row['valor']):08d}"
    def create_pending(self, data: SaleInput, user: User) -> Sale:
        doc={"numero":self._number(),"comanda_id":data.command_id,"cliente_id":data.customer_id,"cliente_nome":data.customer_name,"itens":[{"produto_id":i.product_id,"produto_nome":i.product_name,"tipo_embalagem":i.package_type.value,"quantidade":i.quantity,"unidades_por_fardo":i.units_per_pack,"quantidade_unidades":i.converted_units,"preco":Decimal128(i.unit_price),"desconto":Decimal128(i.discount),"total":Decimal128(i.total)} for i in data.items],"subtotal":Decimal128(data.subtotal),"desconto":Decimal128(data.total_discount),"acrescimo":Decimal128(data.surcharge),"taxa_entrega":Decimal128(data.delivery_fee),"total":Decimal128(data.total),"troco":Decimal128(data.change),"pagamentos":[{"forma":p.method.value,"valor":Decimal128(p.amount),"parcelas":p.installments} for p in data.payments],"fiado_vencimento":str(data.credit_due_date) if data.credit_due_date else None,"observacoes":data.notes,"status":SaleStatus.PENDING.value,"usuario_id":user.id,"usuario":user.username,"data_hora":utc_now()}
        result=self.sales.insert_one(doc); doc["_id"]=result.inserted_id; return self._model(doc)
    def complete(self, sale_id: str) -> Sale:
        from bson import ObjectId
        key=ObjectId(sale_id) if ObjectId.is_valid(sale_id) else sale_id; doc=self.sales.find_one_and_update({"_id":key,"status":SaleStatus.PENDING.value},{"$set":{"status":SaleStatus.COMPLETED.value,"concluida_em":utc_now()}},return_document=ReturnDocument.AFTER)
        if not doc: raise ValueError("Venda não está pendente.")
        return self._model(doc)
    def fail(self,sale_id):
        from bson import ObjectId
        self.sales.update_one({"_id":ObjectId(sale_id) if ObjectId.is_valid(sale_id) else sale_id},{"$set":{"status":SaleStatus.FAILED.value}})
    def _model(self,d):
        items=[SaleItem(product_id=i["produto_id"],product_name=i["produto_nome"],package_type=i["tipo_embalagem"],quantity=i["quantidade"],units_per_pack=i.get("unidades_por_fardo"),unit_price=_dec(i["preco"]),discount=_dec(i.get("desconto"))) for i in d["itens"]]
        payments=[SalePayment(method=p["forma"],amount=_dec(p["valor"]),installments=p.get("parcelas",1)) for p in d["pagamentos"]]
        return Sale(id=str(d["_id"]),number=d["numero"],customer_id=d.get("cliente_id"),customer_name=d.get("cliente_nome"),items=items,total_discount=_dec(d.get("desconto")),surcharge=_dec(d.get("acrescimo")),delivery_fee=_dec(d.get("taxa_entrega")),notes=d.get("observacoes"),payments=payments,status=d["status"],created_by=d.get("usuario") or "",created_at=d["data_hora"],completed_at=d.get("concluida_em"))
