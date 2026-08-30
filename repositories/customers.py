"""Persistência MongoDB do módulo de clientes."""

from __future__ import annotations

import re
from datetime import datetime, time, timezone
from decimal import Decimal
from typing import Any

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from models.auth import utc_now
from models.customer import Address, Customer, CustomerInput, CustomerPage
from models.credit import CreditCustomerStatus,CreditProfile
from bson.decimal128 import Decimal128


class DuplicateCustomerError(RuntimeError):
    """CPF já cadastrado para outro cliente."""


def _id(value: str) -> ObjectId | str:
    return ObjectId(value) if ObjectId.is_valid(value) else value


def _address(document: dict[str, Any] | None) -> Address | None:
    return Address.model_validate(document) if document else None

def _decimal(value) -> Decimal:
    if value is None:return Decimal("0")
    return value.to_decimal() if isinstance(value,Decimal128) else Decimal(str(value))


class CustomerRepository:
    def __init__(self, database: Database) -> None:
        self._customers = database["clientes"]
        self._sales = database["vendas"]

    @staticmethod
    def _to_model(document: dict[str, Any]) -> Customer:
        birth_value = document.get("data_nascimento")
        birth_date = birth_value.date() if isinstance(birth_value, datetime) else birth_value
        return Customer(
            id=str(document["_id"]), full_name=document.get("nome_completo"), cpf=document.get("cpf"),
            birth_date=birth_date, phone=document["telefone"], whatsapp=document.get("whatsapp"),
            email=document.get("email"), main_address=_address(document.get("endereco_principal")),
            additional_addresses=[Address.model_validate(item) for item in document.get("enderecos_adicionais", [])],
            notes=document.get("observacoes"), age_confirmed=document.get("maioridade_confirmada", False),
            active=document.get("ativo", True), created_at=document["criado_em"], updated_at=document["atualizado_em"],
            total_spent=Decimal(str(document.get("total_gasto", 0))), average_ticket=Decimal(str(document.get("ticket_medio", 0))),
            last_purchase_at=document.get("ultima_compra"),
            credit=CreditProfile(enabled=document.get("fiado_habilitado",False),credit_limit=_decimal(document.get("fiado_limite_credito")),debt_balance=_decimal(document.get("fiado_saldo_devedor")),default_due_day=document.get("fiado_dia_vencimento"),due_days=document.get("fiado_dias_vencimento",30),allow_overdue_purchase=document.get("fiado_permitir_vencido",False),status=document.get("fiado_status",CreditCustomerStatus.INACTIVE.value),block_reason=document.get("fiado_motivo_bloqueio"),blocked_at=document.get("fiado_bloqueado_em"),blocked_by=document.get("fiado_bloqueado_por"),financial_notes=document.get("fiado_observacoes"),over_limit_amount=_decimal(document.get("fiado_excesso_limite"))),
        )

    @staticmethod
    def _document(data: CustomerInput) -> dict[str, Any]:
        birth_datetime = datetime.combine(data.birth_date, time.min, tzinfo=timezone.utc) if data.birth_date else None
        return {
            "nome_completo": data.full_name, "nome_normalizado": data.full_name.casefold() if data.full_name else None, "cpf": data.cpf,
            "data_nascimento": birth_datetime, "telefone": data.phone, "whatsapp": data.whatsapp,
            "email": data.email, "endereco_principal": data.main_address.model_dump() if data.main_address else None,
            "enderecos_adicionais": [item.model_dump() for item in data.additional_addresses],
            "observacoes": data.notes, "maioridade_confirmada": data.age_confirmed, "ativo": data.active,
            "fiado_habilitado":data.credit.enabled,"fiado_limite_credito":Decimal128(data.credit.credit_limit),"fiado_dia_vencimento":data.credit.default_due_day,"fiado_dias_vencimento":data.credit.due_days,"fiado_permitir_vencido":data.credit.allow_overdue_purchase,"fiado_status":data.credit.status.value,"fiado_motivo_bloqueio":data.credit.block_reason,"fiado_bloqueado_em":data.credit.blocked_at,"fiado_bloqueado_por":data.credit.blocked_by,"fiado_observacoes":data.credit.financial_notes,
        }

    def create(self, data: CustomerInput) -> Customer:
        now = utc_now()
        document = self._document(data) | {"criado_em": now, "atualizado_em": now}
        try:
            result = self._customers.insert_one(document)
        except DuplicateKeyError as exc:
            raise DuplicateCustomerError("Já existe um cliente com este CPF.") from exc
        document["_id"] = result.inserted_id
        return self._to_model(document)

    def update(self, customer_id: str, data: CustomerInput) -> Customer | None:
        fields = self._document(data) | {"atualizado_em": utc_now()}
        try:
            document = self._customers.find_one_and_update({"_id": _id(customer_id)}, {"$set": fields}, return_document=ReturnDocument.AFTER)
        except DuplicateKeyError as exc:
            raise DuplicateCustomerError("Já existe um cliente com este CPF.") from exc
        return self._to_model(document) if document else None

    def get(self, customer_id: str) -> Customer | None:
        document = self._customers.find_one({"_id": _id(customer_id)})
        if not document:
            return None
        metrics = self._metrics(customer_id)
        document.update(metrics)
        return self._to_model(document)

    def list_page(self, *, search: str = "", active: bool | None = True, page: int = 1, page_size: int = 20) -> CustomerPage:
        query: dict[str, Any] = {}
        if active is not None:
            query["ativo"] = active
        if search.strip():
            safe = re.escape(search.strip())
            query["$or"] = [{"nome_completo": {"$regex": safe, "$options": "i"}}, {"cpf": {"$regex": re.sub(r"\D", "", safe)}}, {"telefone": {"$regex": re.sub(r"\D", "", safe)}}]
        total = self._customers.count_documents(query)
        items = self._customers.find(query).sort("nome_completo", 1).skip((page - 1) * page_size).limit(page_size)
        models: list[Customer] = []
        for document in items:
            document.update(self._metrics(str(document["_id"])))
            models.append(self._to_model(document))
        return CustomerPage(items=models, total=total, page=page, page_size=page_size)

    def set_active(self, customer_id: str, active: bool) -> bool:
        result = self._customers.update_one({"_id": _id(customer_id)}, {"$set": {"ativo": active, "atualizado_em": utc_now()}})
        return result.matched_count == 1

    def purchase_history(self, customer_id: str, limit: int = 50) -> list[dict[str, Any]]:
        projection = {"numero": 1, "data_hora": 1, "total": 1, "status": 1, "itens": 1}
        return list(self._sales.find({"cliente_id": customer_id}, projection).sort("data_hora", -1).limit(limit))

    def _metrics(self, customer_id: str) -> dict[str, Any]:
        rows = list(self._sales.aggregate([
            {"$match": {"cliente_id": customer_id, "status": {"$nin": ["cancelada", "cancelado"]}}},
            {"$group": {"_id": None, "total_gasto": {"$sum": "$total"}, "quantidade": {"$sum": 1}, "ultima_compra": {"$max": "$data_hora"}}},
        ]))
        if not rows:
            return {"total_gasto": 0, "ticket_medio": 0, "ultima_compra": None}
        row = rows[0]
        count = int(row.get("quantidade", 0))
        total = Decimal(str(row.get("total_gasto", 0)))
        return {"total_gasto": total, "ticket_medio": total / count if count else 0, "ultima_compra": row.get("ultima_compra")}
