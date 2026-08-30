"""Persistência MongoDB de usuários, perfis e auditoria."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from bson import ObjectId
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from models.auth import Permission, Profile, ProfileCode, User, utc_now


class DuplicateUserError(RuntimeError):
    """Usuário ou e-mail já existe."""


def _identifier(value: str) -> ObjectId | str:
    return ObjectId(value) if ObjectId.is_valid(value) else value


class UserRepository:
    """Única camada autorizada a acessar a coleção de usuários."""

    def __init__(self, database: Database) -> None:
        self._collection = database["usuarios"]

    @staticmethod
    def _to_user(document: dict[str, Any]) -> User:
        return User(
            id=str(document["_id"]),
            username=document["usuario"],
            email=document["email"],
            full_name=document["nome_completo"],
            profile_code=document["perfil_codigo"],
            individual_grants=set(document.get("permissoes_liberadas", [])),
            individual_denials=set(document.get("permissoes_bloqueadas", [])),
            active=document.get("ativo", True),
            must_change_password=document.get("alterar_senha", True),
            failed_attempts=document.get("tentativas_falhas", 0),
            locked_until=document.get("bloqueado_ate"),
            last_access_at=document.get("ultimo_acesso"),
            created_at=document["criado_em"],
            updated_at=document["atualizado_em"],
        )

    def count(self) -> int:
        return self._collection.count_documents({})

    def find_by_login(self, login: str) -> tuple[User, str] | None:
        normalized = login.strip().lower()
        document = self._collection.find_one(
            {"$or": [{"usuario": normalized}, {"email_normalizado": normalized}]}
        )
        if not document:
            return None
        return self._to_user(document), document["senha_hash"]

    def get(self, user_id: str) -> User | None:
        document = self._collection.find_one({"_id": _identifier(user_id)})
        return self._to_user(document) if document else None

    def list_all(self) -> list[User]:
        return [self._to_user(item) for item in self._collection.find().sort("nome_completo", 1)]

    def create(self, user: User, password_hash: str) -> User:
        document = {
            "usuario": user.username.lower(),
            "email": str(user.email),
            "email_normalizado": str(user.email).lower(),
            "nome_completo": user.full_name,
            "perfil_codigo": user.profile_code.value,
            "permissoes_liberadas": [item.value for item in user.individual_grants],
            "permissoes_bloqueadas": [item.value for item in user.individual_denials],
            "senha_hash": password_hash,
            "ativo": user.active,
            "alterar_senha": user.must_change_password,
            "tentativas_falhas": user.failed_attempts,
            "bloqueado_ate": user.locked_until,
            "ultimo_acesso": user.last_access_at,
            "criado_em": user.created_at,
            "atualizado_em": user.updated_at,
        }
        try:
            result = self._collection.insert_one(document)
        except DuplicateKeyError as exc:
            raise DuplicateUserError("Usuário ou e-mail já cadastrado.") from exc
        user.id = str(result.inserted_id)
        return user


    def update_login_state(
        self,
        user_id: str,
        *,
        failed_attempts: int,
        locked_until: datetime | None,
        last_access_at: datetime | None = None,
    ) -> None:
        fields: dict[str, Any] = {
            "tentativas_falhas": failed_attempts,
            "bloqueado_ate": locked_until,
            "atualizado_em": utc_now(),
        }
        if last_access_at is not None:
            fields["ultimo_acesso"] = last_access_at
        self._collection.update_one({"_id": _identifier(user_id)}, {"$set": fields})

    def change_password(self, user_id: str, password_hash: str, force_change: bool) -> None:
        self._collection.update_one(
            {"_id": _identifier(user_id)},
            {"$set": {"senha_hash": password_hash, "alterar_senha": force_change, "atualizado_em": utc_now()}},
        )

    def set_active(self, user_id: str, active: bool) -> None:
        self._collection.update_one(
            {"_id": _identifier(user_id)},
            {"$set": {"ativo": active, "atualizado_em": utc_now()}},
        )

    def update_permissions(self, user_id: str, grants: set[Permission], denials: set[Permission]) -> None:
        self._collection.update_one(
            {"_id": _identifier(user_id)},
            {"$set": {
                "permissoes_liberadas": [item.value for item in grants],
                "permissoes_bloqueadas": [item.value for item in denials],
                "atualizado_em": utc_now(),
            }},
        )


class ProfileRepository:
    def __init__(self, database: Database) -> None:
        self._collection = database["perfis"]

    def upsert(self, profile: Profile) -> None:
        self._collection.update_one(
            {"codigo": profile.code.value},
            {"$set": {"nome": profile.name, "permissoes": [p.value for p in profile.permissions], "sistema": profile.system, "ativo": profile.active}},
            upsert=True,
        )

    def get(self, code: ProfileCode) -> Profile | None:
        item = self._collection.find_one({"codigo": code.value, "ativo": True})
        if not item:
            return None
        return Profile(id=str(item["_id"]), code=item["codigo"], name=item["nome"], permissions=set(item["permissoes"]), system=item.get("sistema", True), active=item.get("ativo", True))


class AuditRepository:
    def __init__(self, database: Database) -> None:
        self._collection = database["auditoria"]

    def record(self, *, user: User | None, action: str, module: str, affected_id: str | None = None, reason: str | None = None, details: dict[str, Any] | None = None) -> None:
        self._collection.insert_one({
            "usuario_id": user.id if user else None,
            "usuario": user.username if user else "sistema",
            "perfil": user.profile_code.value if user else "sistema",
            "acao": action,
            "modulo": module,
            "registro_afetado": affected_id,
            "motivo": reason,
            "detalhes": details or {},
            "data_hora": utc_now(),
        })
