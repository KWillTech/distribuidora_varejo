"""Persistência MongoDB de fornecedores e seu histórico de compras."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from models.auth import utc_now
from models.customer import Address
from models.supplier import Supplier, SupplierInput, SupplierPage


class DuplicateSupplierError(RuntimeError):
    """Documento já pertence a outro fornecedor."""


def _id(value: str) -> ObjectId | str:
    return ObjectId(value) if ObjectId.is_valid(value) else value


class SupplierRepository:
    def __init__(self, database: Database) -> None:
        self._suppliers = database["fornecedores"]
        self._purchases = database["compras"]

    @staticmethod
    def _document(data: SupplierInput) -> dict[str, Any]:
        return {
            "razao_social": data.legal_name, "nome_fantasia": data.trade_name, "documento": data.document,
            "inscricao_estadual": data.state_registration, "telefone": data.phone, "whatsapp": data.whatsapp,
            "email": data.email, "endereco": data.address.model_dump() if data.address else None,
            "contato_comercial": data.commercial_contact, "prazo_entrega": data.delivery_term,
            "condicao_pagamento": data.payment_terms, "observacoes": data.notes, "ativo": data.active,
        }

    @staticmethod
    def _to_model(document: dict[str, Any]) -> Supplier:
        return Supplier(
            id=str(document["_id"]), legal_name=document["razao_social"], trade_name=document.get("nome_fantasia"),
            document=document["documento"], state_registration=document.get("inscricao_estadual"), phone=document.get("telefone"),
            whatsapp=document.get("whatsapp"), email=document.get("email"),
            address=Address.model_validate(document["endereco"]) if document.get("endereco") else None,
            commercial_contact=document.get("contato_comercial"), delivery_term=document.get("prazo_entrega"),
            payment_terms=document.get("condicao_pagamento"), notes=document.get("observacoes"), active=document.get("ativo", True),
            created_at=document["criado_em"], updated_at=document["atualizado_em"],
            purchase_count=int(document.get("quantidade_compras", 0)), total_purchased=Decimal(str(document.get("total_comprado", 0))),
            last_purchase_at=document.get("ultima_compra"),
        )

    def create(self, data: SupplierInput) -> Supplier:
        now = utc_now(); document = self._document(data) | {"criado_em": now, "atualizado_em": now}
        try: result = self._suppliers.insert_one(document)
        except DuplicateKeyError as exc: raise DuplicateSupplierError("CPF ou CNPJ já cadastrado.") from exc
        document["_id"] = result.inserted_id
        return self._to_model(document)

    def update(self, supplier_id: str, data: SupplierInput) -> Supplier | None:
        try:
            document = self._suppliers.find_one_and_update({"_id": _id(supplier_id)}, {"$set": self._document(data) | {"atualizado_em": utc_now()}}, return_document=ReturnDocument.AFTER)
        except DuplicateKeyError as exc: raise DuplicateSupplierError("CPF ou CNPJ já cadastrado.") from exc
        return self._to_model(document) if document else None

    def get(self, supplier_id: str) -> Supplier | None:
        document = self._suppliers.find_one({"_id": _id(supplier_id)})
        if not document: return None
        document.update(self._metrics(supplier_id))
        return self._to_model(document)

    def list_page(self, *, search: str = "", active: bool | None = True, page: int = 1, page_size: int = 20) -> SupplierPage:
        query: dict[str, Any] = {}
        if active is not None: query["ativo"] = active
        if search.strip():
            safe = re.escape(search.strip()); digits = re.sub(r"\D", "", search)
            terms = [{"razao_social": {"$regex": safe, "$options": "i"}}, {"nome_fantasia": {"$regex": safe, "$options": "i"}}]
            if digits: terms.append({"documento": {"$regex": digits}})
            query["$or"] = terms
        total = self._suppliers.count_documents(query)
        cursor = self._suppliers.find(query).sort("razao_social", 1).skip((page - 1) * page_size).limit(page_size)
        items = []
        for document in cursor:
            document.update(self._metrics(str(document["_id"])))
            items.append(self._to_model(document))
        return SupplierPage(items=items, total=total, page=page, page_size=page_size)

    def set_active(self, supplier_id: str, active: bool) -> bool:
        result = self._suppliers.update_one({"_id": _id(supplier_id)}, {"$set": {"ativo": active, "atualizado_em": utc_now()}})
        return result.matched_count == 1

    def purchase_history(self, supplier_id: str, limit: int = 50) -> list[dict[str, Any]]:
        return list(self._purchases.find({"fornecedor_id": supplier_id}, {"numero_nota": 1, "data_hora": 1, "total": 1, "status": 1, "itens": 1}).sort("data_hora", -1).limit(limit))

    def latest_costs(self, supplier_id: str, limit: int = 30) -> list[dict[str, Any]]:
        rows = self._purchases.aggregate([
            {"$match": {"fornecedor_id": supplier_id, "status": {"$ne": "cancelada"}}}, {"$unwind": "$itens"},
            {"$sort": {"data_hora": -1}},
            {"$group": {"_id": "$itens.produto_id", "produto": {"$first": "$itens.produto_nome"}, "custo_unitario": {"$first": "$itens.custo_unitario"}, "data_hora": {"$first": "$data_hora"}}},
            {"$sort": {"data_hora": -1}}, {"$limit": limit},
        ])
        return list(rows)

    def _metrics(self, supplier_id: str) -> dict[str, Any]:
        rows = list(self._purchases.aggregate([{"$match": {"fornecedor_id": supplier_id, "status": {"$ne": "cancelada"}}}, {"$group": {"_id": None, "quantidade_compras": {"$sum": 1}, "total_comprado": {"$sum": "$total"}, "ultima_compra": {"$max": "$data_hora"}}}]))
        return rows[0] if rows else {"quantidade_compras": 0, "total_comprado": 0, "ultima_compra": None}

    def active_options(self) -> list[tuple[str, str, str | None]]:
        return [(str(item["_id"]), item.get("nome_fantasia") or item["razao_social"], item.get("whatsapp")) for item in self._suppliers.find({"ativo": True}, {"razao_social": 1, "nome_fantasia": 1, "whatsapp": 1}).sort("razao_social", 1)]
