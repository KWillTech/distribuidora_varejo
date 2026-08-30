"""Persistência atômica de comandas, numeração e reservas de estoque."""
from datetime import datetime,time,timezone
from decimal import Decimal
from bson import ObjectId
from bson.decimal128 import Decimal128
from pymongo import ReturnDocument
from models.auth import utc_now
from models.command import Command,CommandItem,CommandItemInput,CommandOpenInput,CommandStatus,CommandSummary

def _id(v):return ObjectId(v) if ObjectId.is_valid(v) else v
def _dec(v):return v.to_decimal() if isinstance(v,Decimal128) else Decimal(str(v or 0))
class CommandConflictError(RuntimeError):pass
class CommandRepository:
    def __init__(self,database):
        self.commands=database["comandas"]; self.products=database["produtos"]; self.movements=database["movimentacoes_estoque"]; self.settings=database["configuracoes"]
    def _number(self):
        row=self.settings.find_one_and_update({"chave":"sequencia_comanda"},{"$inc":{"valor":1}},upsert=True,return_document=ReturnDocument.AFTER); return f"CMD-{int(row['valor']):06d}"
    def open(self,data:CommandOpenInput,user):
        if data.slot_number and self.commands.count_documents({"posicao":data.slot_number,"status":{"$in":["aberta","em_atendimento","aguardando_pagamento"]}}):raise ValueError(f"Comanda {data.slot_number:02d} já está aberta.")
        if data.customer_id and not data.confirm_duplicate and self.commands.count_documents({"cliente_id":data.customer_id,"status":{"$in":["aberta","em_atendimento","aguardando_pagamento"]}}):raise ValueError("Este cliente já possui uma comanda aberta. Confirme para abrir outra.")
        now=utc_now(); doc={"numero":self._number(),"posicao":data.slot_number,"cliente_id":data.customer_id,"cliente_snapshot":{"nome":data.customer_name,"telefone":data.phone},"identificacao":data.identification or data.customer_name or f"Comanda {data.slot_number or ''}","telefone":data.phone,"quantidade_pessoas":data.people,"tipo_atendimento":data.service_type.value,"usuario_abertura_id":user.id,"usuario_responsavel_id":user.id,"usuario_responsavel":user.username,"data_abertura":now,"data_fechamento":None,"status":CommandStatus.OPEN.value,"itens":[],"subtotal":Decimal128(Decimal("0")),"desconto":Decimal128(Decimal("0")),"acrescimo":Decimal128(Decimal("0")),"taxa_entrega":Decimal128(Decimal("0")),"total":Decimal128(Decimal("0")),"pagamentos":[],"venda_id":None,"observacoes":data.notes,"versao":1,"criado_em":now,"atualizado_em":now}
        result=self.commands.insert_one(doc); doc["_id"]=result.inserted_id; return self._model(doc)
    def get(self,command_id):
        row=self.commands.find_one({"_id":_id(command_id)}); return self._model(row) if row else None
    def list(self,status=None,search=None,limit=500):
        query={};
        if status:query["status"]=status
        if search:query["$or"]=[{"numero":{"$regex":search,"$options":"i"}},{"identificacao":{"$regex":search,"$options":"i"}},{"telefone":{"$regex":search,"$options":"i"}}]
        return [self._model(x) for x in self.commands.find(query).sort("data_abertura",-1).limit(limit)]
    def add_item(self,command_id,version,data:CommandItemInput,user):
        units=data.base_units; product=self.products.find_one_and_update({"_id":_id(data.product_id),"ativo":True,"$expr":{"$gte":[{"$subtract":["$estoque_atual_unidades",{"$ifNull":["$estoque_reservado_unidades",0]}]},units]}},{"$inc":{"estoque_reservado_unidades":units}},return_document=ReturnDocument.BEFORE)
        if not product:raise ValueError("Produto inexistente, inativo ou sem estoque disponível.")
        item={"item_id":str(ObjectId()),"produto_id":data.product_id,"codigo":data.code,"nome_snapshot":data.product_name,"tipo_venda":data.package_type.value,"quantidade":data.quantity,"unidades_por_fardo":data.units_per_pack,"quantidade_base":units,"preco_praticado":Decimal128(data.price),"desconto":Decimal128(data.discount),"subtotal":Decimal128(data.subtotal),"codigo_barras":data.barcode,"observacao":data.notes,"usuario_id":user.id,"usuario":user.username,"adicionado_em":utc_now()}
        updated=self.commands.find_one_and_update({"_id":_id(command_id),"versao":version,"status":{"$in":["aberta","em_atendimento"]}},{"$push":{"itens":item},"$inc":{"subtotal":Decimal128(data.subtotal),"total":Decimal128(data.subtotal),"versao":1},"$set":{"status":"em_atendimento","atualizado_em":utc_now()}},return_document=ReturnDocument.AFTER)
        if not updated:self.products.update_one({"_id":_id(data.product_id)},{"$inc":{"estoque_reservado_unidades":-units}}); raise CommandConflictError("A comanda foi alterada por outro usuário. Atualize e tente novamente.")
        self._reservation_movement(data.product_id,data.product_name,units,user,updated["numero"],"reserva_comanda"); return self._model(updated)
    def remove_item(self,command_id,version,item_id,user,reason):
        current=self.commands.find_one({"_id":_id(command_id),"versao":version,"status":{"$in":["aberta","em_atendimento"]},"itens.item_id":item_id})
        if not current:raise CommandConflictError("Item inexistente ou comanda atualizada por outro usuário.")
        item=next(x for x in current["itens"] if x["item_id"]==item_id); value=_dec(item["subtotal"]); updated=self.commands.find_one_and_update({"_id":current["_id"],"versao":version},{"$pull":{"itens":{"item_id":item_id}},"$inc":{"subtotal":Decimal128(-value),"total":Decimal128(-value),"versao":1},"$set":{"atualizado_em":utc_now()}},return_document=ReturnDocument.AFTER)
        if not updated:raise CommandConflictError("A comanda foi atualizada por outro usuário.")
        self.products.update_one({"_id":_id(item["produto_id"]),"estoque_reservado_unidades":{"$gte":item["quantidade_base"]}},{"$inc":{"estoque_reservado_unidades":-item["quantidade_base"]}}); self._reservation_movement(item["produto_id"],item["nome_snapshot"],-item["quantidade_base"],user,current["numero"],"liberacao_reserva",reason); return self._model(updated)
    def request_close(self,command_id,version):
        row=self.commands.find_one_and_update({"_id":_id(command_id),"versao":version,"status":{"$in":["aberta","em_atendimento"]},"itens":{"$ne":[]}},{"$set":{"status":"aguardando_pagamento","atualizado_em":utc_now()},"$inc":{"versao":1}},return_document=ReturnDocument.AFTER)
        if not row:raise CommandConflictError("Comanda sem itens, encerrada ou alterada por outro usuário.")
        return self._model(row)
    def reopen(self,command_id,version):
        row=self.commands.find_one_and_update({"_id":_id(command_id),"versao":version,"status":"aguardando_pagamento"},{"$set":{"status":"em_atendimento","atualizado_em":utc_now()},"$inc":{"versao":1}},return_document=ReturnDocument.AFTER)
        if not row:raise CommandConflictError("Comanda não pode ser reaberta.")
        return self._model(row)
    def finalize(self,command_id,version,sale):
        row=self.commands.find_one_and_update({"_id":_id(command_id),"versao":version,"status":"aguardando_pagamento","venda_id":None},{"$set":{"status":"finalizada","venda_id":sale.id,"pagamentos":[{"forma":p.method.value,"valor":Decimal128(p.amount)} for p in sale.payments],"data_fechamento":utc_now(),"atualizado_em":utc_now()},"$inc":{"versao":1}},return_document=ReturnDocument.AFTER)
        if not row:raise CommandConflictError("Comanda já finalizada ou alterada por outro usuário.")
        for item in row["itens"]:self.products.update_one({"_id":_id(item["produto_id"]),"estoque_reservado_unidades":{"$gte":item["quantidade_base"]}},{"$inc":{"estoque_reservado_unidades":-item["quantidade_base"]}})
        return self._model(row)
    def cancel(self,command_id,version,user,reason):
        row=self.commands.find_one_and_update({"_id":_id(command_id),"versao":version,"status":{"$in":["aberta","em_atendimento","aguardando_pagamento"]}},{"$set":{"status":"cancelada","motivo_cancelamento":reason,"cancelada_por":user.username,"cancelada_em":utc_now(),"atualizado_em":utc_now()},"$inc":{"versao":1}},return_document=ReturnDocument.AFTER)
        if not row:raise CommandConflictError("Comanda não pode ser cancelada.")
        for item in row["itens"]:self.products.update_one({"_id":_id(item["produto_id"]),"estoque_reservado_unidades":{"$gte":item["quantidade_base"]}},{"$inc":{"estoque_reservado_unidades":-item["quantidade_base"]}}); self._reservation_movement(item["produto_id"],item["nome_snapshot"],-item["quantidade_base"],user,row["numero"],"liberacao_cancelamento",reason)
        return self._model(row)
    def transfer_all(self,source_id,target_id,source_version,target_version,user,reason):
        source=self.commands.find_one({"_id":_id(source_id),"versao":source_version,"status":{"$in":["aberta","em_atendimento"]}}); target=self.commands.find_one({"_id":_id(target_id),"versao":target_version,"status":{"$in":["aberta","em_atendimento"]}})
        if not source or not target or source_id==target_id:raise CommandConflictError("Comandas inválidas ou atualizadas.")
        amount=_dec(source["total"]); changed=self.commands.update_one({"_id":target["_id"],"versao":target_version},{"$push":{"itens":{"$each":source["itens"]}},"$inc":{"subtotal":Decimal128(_dec(source["subtotal"])),"total":Decimal128(amount),"versao":1},"$set":{"status":"em_atendimento","atualizado_em":utc_now()}})
        if changed.modified_count!=1:raise CommandConflictError("Destino alterado por outro usuário.")
        closed=self.commands.update_one({"_id":source["_id"],"versao":source_version},{"$set":{"status":"unificada","unificada_em":utc_now(),"unificada_destino_id":str(target["_id"]),"motivo_uniao":reason,"atualizado_em":utc_now()},"$inc":{"versao":1}})
        if closed.modified_count!=1:raise CommandConflictError("Origem alterada; atualize as comandas.")
        return self.get(target_id)
    def summary(self):
        today=datetime.combine(datetime.now(timezone.utc).date(),time.min,tzinfo=timezone.utc); active=list(self.commands.find({"status":{"$in":["aberta","em_atendimento","aguardando_pagamento"]}})); finalized=list(self.commands.find({"status":"finalizada","data_fechamento":{"$gte":today}})); durations=[(x["data_fechamento"]-x["data_abertura"]).total_seconds()/60 for x in finalized if x.get("data_fechamento")]
        return CommandSummary(open=sum(x["status"]=="aberta" for x in active),serving=sum(x["status"]=="em_atendimento" for x in active),awaiting=sum(x["status"]=="aguardando_pagamento" for x in active),finalized_today=len(finalized),open_value=sum((_dec(x.get("total")) for x in active),Decimal("0")),average_minutes=Decimal(str(round(sum(durations)/len(durations),1))) if durations else Decimal("0"))
    def _reservation_movement(self,product_id,name,units,user,number,kind,reason=None):self.movements.insert_one({"produto_id":product_id,"produto_nome":name,"tipo_movimentacao":kind,"tipo_embalagem":"unidade","quantidade_informada":abs(units),"quantidade_convertida_unidades":units,"motivo":reason or f"Comanda {number}","usuario_id":user.id,"usuario":user.username,"data_hora":utc_now(),"documento_relacionado":number})
    @staticmethod
    def _model(d):
        items=[CommandItem(item_id=x["item_id"],product_id=x["produto_id"],code=x.get("codigo","") ,product_name=x["nome_snapshot"],package_type=x["tipo_venda"],quantity=x["quantidade"],units_per_pack=x.get("unidades_por_fardo"),price=_dec(x["preco_praticado"]),discount=_dec(x.get("desconto")),barcode=x.get("codigo_barras"),notes=x.get("observacao"),user_id=x.get("usuario_id"),username=x.get("usuario","") ,added_at=x["adicionado_em"]) for x in d.get("itens",[])]
        snap=d.get("cliente_snapshot") or {}; payments=[{"forma":p.get("forma"),"valor":_dec(p.get("valor"))} for p in d.get("pagamentos",[])]; return Command(id=str(d["_id"]),number=d["numero"],slot_number=d.get("posicao"),customer_id=d.get("cliente_id"),customer_name=snap.get("nome"),identification=d.get("identificacao") or snap.get("nome") or "Cliente",phone=d.get("telefone"),people=d.get("quantidade_pessoas"),service_type=d["tipo_atendimento"],opened_by_id=d.get("usuario_abertura_id"),opened_by=d.get("usuario_responsavel","") ,opened_at=d["data_abertura"],closed_at=d.get("data_fechamento"),status=d["status"],items=items,discount=_dec(d.get("desconto")),surcharge=_dec(d.get("acrescimo")),delivery_fee=_dec(d.get("taxa_entrega")),payments=payments,sale_id=d.get("venda_id"),notes=d.get("observacoes"),version=d.get("versao",1))
