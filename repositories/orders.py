"""Persistência de pedidos e entregas."""
from datetime import datetime,timezone
from bson import ObjectId
from bson.decimal128 import Decimal128
from pymongo import DESCENDING
from models.auth import User,utc_now
from models.order import Order,OrderInput,OrderStatus

def _id(value):
    try:return ObjectId(value)
    except Exception:return value
def _dec(value): return value.to_decimal() if isinstance(value,Decimal128) else value

class OrderRepository:
    def __init__(self,database): self.orders=database["pedidos"]; self.deliveries=database["entregas"]
    def _number(self):
        last=self.orders.find_one(sort=[("data_hora",DESCENDING)]); sequence=int((last or {}).get("numero","PED-00000000").split("-")[-1])+1; return f"PED-{sequence:08d}"
    def create(self,data:OrderInput,user:User):
        doc={"numero":self._number(),"cliente_nome":data.customer_name,"telefone":data.phone,"endereco":data.address,"referencia":data.reference,"produtos":data.products,"volumes":data.volumes,"taxa_entrega":Decimal128(data.delivery_fee),"forma_pagamento":data.payment_method,"troco_para":Decimal128(data.change_for) if data.change_for is not None else None,"observacoes":data.notes,"status":OrderStatus.AWAITING_PAYMENT.value,"entregador_id":None,"entregador_nome":None,"ocorrencias":[],"criado_por":user.username,"data_hora":utc_now()}
        result=self.orders.insert_one(doc); doc["_id"]=result.inserted_id
        self.deliveries.insert_one({**{key:value for key,value in doc.items() if key!="_id"},"pedido_id":result.inserted_id,"criado_em":doc["data_hora"]})
        return self._model(doc)
    def list(self,delivery_person_id=None,created_by=None):
        query={"entregador_id":delivery_person_id} if delivery_person_id else ({"criado_por":created_by} if created_by else {}); return [self._model(d) for d in self.orders.find(query).sort("data_hora",DESCENDING)]
    def get(self,order_id):
        doc=self.orders.find_one({"_id":_id(order_id)}); return self._model(doc) if doc else None
    def assign(self,order_id,person_id,name):
        oid=_id(order_id); fields={"entregador_id":person_id,"entregador_nome":name}; self.orders.update_one({"_id":oid},{"$set":fields}); self.deliveries.update_one({"pedido_id":oid},{"$set":fields}); return self.get(order_id)
    def update_status(self,order_id,status):
        fields={"status":status.value}
        if status==OrderStatus.OUT_FOR_DELIVERY:fields["saida_em"]=utc_now()
        if status==OrderStatus.DELIVERED:fields["entregue_em"]=utc_now()
        oid=_id(order_id); self.orders.update_one({"_id":oid},{"$set":fields}); self.deliveries.update_one({"pedido_id":oid},{"$set":fields}); return self.get(order_id)
    def occurrence(self,order_id,text):
        oid=_id(order_id); occurrence=f"{utc_now().strftime('%d/%m/%Y %H:%M')} - {text}"; self.orders.update_one({"_id":oid},{"$push":{"ocorrencias":occurrence}}); self.deliveries.update_one({"pedido_id":oid},{"$push":{"ocorrencias":occurrence}}); return self.get(order_id)
    @staticmethod
    def _model(d):
        return Order(id=str(d["_id"]),number=d["numero"],customer_name=d["cliente_nome"],phone=d["telefone"],address=d["endereco"],reference=d.get("referencia"),products=d["produtos"],volumes=d["volumes"],delivery_fee=_dec(d.get("taxa_entrega")),payment_method=d["forma_pagamento"],change_for=_dec(d.get("troco_para")),notes=d.get("observacoes"),status=d["status"],delivery_person_id=d.get("entregador_id"),delivery_person_name=d.get("entregador_nome"),occurrences=d.get("ocorrencias",[]),created_by=d["criado_por"],created_at=d["data_hora"],departed_at=d.get("saida_em"),delivered_at=d.get("entregue_em"))
