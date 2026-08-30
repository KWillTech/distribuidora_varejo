"""Persistência de auditoria e configurações operacionais."""
from datetime import datetime,time,timedelta,timezone
class AdministrationRepository:
    def __init__(self,database):self.database=database; self.audit=database["auditoria"]; self.settings=database["configuracoes"]
    def audit_list(self,start,end,module=None,search=""):
        begin=datetime.combine(start,time.min,tzinfo=timezone.utc); finish=datetime.combine(end+timedelta(days=1),time.min,tzinfo=timezone.utc); query={"data_hora":{"$gte":begin,"$lt":finish}}
        if module:query["modulo"]=module
        if search:query["$or"]=[{"usuario":{"$regex":search,"$options":"i"}},{"acao":{"$regex":search,"$options":"i"}},{"motivo":{"$regex":search,"$options":"i"}}]
        return list(self.audit.find(query).sort("data_hora",-1).limit(5000))
    def get_settings(self):return {d["chave"]:d.get("valor") for d in self.settings.find({"chave":{"$regex":r"^app\."}})}
    def save_settings(self,values):
        for key,value in values.items():self.settings.update_one({"chave":key},{"$set":{"valor":value,"atualizado_em":datetime.now(timezone.utc)}},upsert=True)
