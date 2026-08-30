"""Auditoria, configurações e backups validados."""
import hashlib,json,zipfile
from datetime import datetime,timezone
from pathlib import Path
from bson import json_util
from models.auth import Permission
from services.rbac import require_permission
class AdministrationService:
    MAX_BACKUP_SIZE=250*1024*1024
    ALLOWED_COLLECTIONS={"comandas","usuarios","perfis","permissoes","auditoria","configuracoes","vendas","itens_venda","pagamentos","pedidos","entregas","produtos","categorias","clientes","fornecedores","compras","contas_pagar","contas_receber","movimentacoes_fiado","pagamentos_fiado","despesas","receitas","pagamentos_financeiros","caixas","movimentacoes_caixa","movimentacoes_estoque","lotes"}
    def __init__(self,repository,audit):self.repository=repository; self.audit=audit
    def audit_list(self,session,start,end,module=None,search=""):require_permission(session,Permission.AUDIT_VIEW); return self.repository.audit_list(start,end,module,search)
    def get_settings(self,session):require_permission(session,Permission.SETTINGS_MANAGE); return self.repository.get_settings()
    def save_settings(self,session,values):
        require_permission(session,Permission.SETTINGS_MANAGE); allowed={"app.estoque_alerta_dias","app.backup_automatico","app.backup_diretorio","app.empresa_nome"}; clean={k:v for k,v in values.items() if k in allowed}; self.repository.save_settings(clean); self.audit.record(user=session.user,action="configuracoes_alteradas",module="configuracoes",details={"chaves":list(clean)}); return clean
    def create_backup(self,session,path):
        require_permission(session,Permission.BACKUP_CREATE); path=Path(path); payload={}
        for name in self.repository.database.list_collection_names():
            if name in self.ALLOWED_COLLECTIONS:payload[name]=json_util.dumps(list(self.repository.database[name].find()),ensure_ascii=False)
        manifest={"format":"adega-backup-v1","created_at":datetime.now(timezone.utc).isoformat(),"collections":sorted(payload)}; digest=hashlib.sha256("".join(payload[name] for name in sorted(payload)).encode()).hexdigest(); manifest["sha256"]=digest
        with zipfile.ZipFile(path,"w",zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json",json.dumps(manifest,ensure_ascii=False,indent=2))
            for name,content in payload.items():archive.writestr(f"collections/{name}.json",content)
        self.audit.record(user=session.user,action="backup_criado",module="backup",details={"arquivo":str(path),"colecoes":len(payload)}); return path
    def validate_backup(self,path):
        try:
            with zipfile.ZipFile(path) as archive:
                manifest=json.loads(archive.read("manifest.json")); names=manifest["collections"]; payload={name:archive.read(f"collections/{name}.json").decode() for name in names}; digest=hashlib.sha256("".join(payload[name] for name in sorted(payload)).encode()).hexdigest()
                if manifest.get("format")!="adega-backup-v1" or digest!=manifest.get("sha256"):raise ValueError("Checksum do backup inválido.")
                if not set(names)<=self.ALLOWED_COLLECTIONS:raise ValueError("Backup contém coleções não permitidas.")
                if sum(info.file_size for info in archive.infolist())>self.MAX_BACKUP_SIZE:raise ValueError("Backup excede o limite de segurança de 250 MB.")
                for content in payload.values():json_util.loads(content)
                return manifest,payload
        except (KeyError,zipfile.BadZipFile,json.JSONDecodeError) as exc:raise ValueError("Arquivo de backup inválido.") from exc
    def restore_backup(self,session,path,confirmation):
        require_permission(session,Permission.BACKUP_RESTORE)
        if confirmation!="RESTAURAR":raise ValueError("Digite RESTAURAR para confirmar.")
        manifest,payload=self.validate_backup(path)
        for name,content in payload.items():
            documents=json_util.loads(content); collection=self.repository.database[name]; collection.delete_many({})
            if documents:collection.insert_many(documents)
        self.audit.record(user=session.user,action="backup_restaurado",module="backup",details={"arquivo":str(path),"colecoes":len(payload)}); return manifest
