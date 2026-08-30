"""Persistência de compras e contas a pagar originadas no recebimento."""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any

from bson import ObjectId
from bson.decimal128 import Decimal128
from pymongo import ReturnDocument
from pymongo.database import Database

from models.auth import User, utc_now
from models.purchase import Purchase, PurchaseInput, PurchaseItem, PurchaseStatus


def _id(value: str) -> ObjectId | str: return ObjectId(value) if ObjectId.is_valid(value) else value
def _decimal(value: Any) -> Decimal:
    if value is None: return Decimal("0")
    return value.to_decimal() if isinstance(value, Decimal128) else Decimal(str(value))


class PurchaseRepository:
    def __init__(self, database: Database) -> None:
        self._purchases = database["compras"]; self._payables = database["contas_pagar"]; self._settings = database["configuracoes"]

    def _next_number(self) -> str:
        counter = self._settings.find_one_and_update({"chave": "sequencia_compra"}, {"$inc": {"valor": 1}, "$setOnInsert": {"criado_em": utc_now()}}, upsert=True, return_document=ReturnDocument.AFTER)
        return f"CP-{int(counter['valor']):08d}"

    @staticmethod
    def _item_document(item: PurchaseItem) -> dict[str, Any]:
        expiry = datetime.combine(item.expiration_date, time.min, tzinfo=timezone.utc) if item.expiration_date else None
        return {"produto_id": item.product_id, "produto_nome": item.product_name, "tipo_embalagem": item.package_type.value, "quantidade": item.quantity, "unidades_por_fardo": item.units_per_pack, "quantidade_unidades": item.converted_units, "custo_embalagem": Decimal128(item.cost_per_package), "custo_unitario": Decimal128(item.unit_cost), "total": Decimal128(item.total), "lote": item.lot_code, "data_validade": expiry}

    def create_pending(self, data: PurchaseInput, user: User) -> Purchase:
        now = utc_now(); number = self._next_number(); document = {"numero": number, "fornecedor_id": data.supplier_id, "fornecedor_nome": data.supplier_name, "fornecedor_whatsapp": data.supplier_whatsapp, "numero_nota": data.invoice_number, "numeros_notas": [data.invoice_number] if data.invoice_number else [], "itens": [self._item_document(item) for item in data.items], "subtotal": Decimal128(data.subtotal), "desconto": Decimal128(data.discount), "frete": Decimal128(data.freight), "total": Decimal128(data.total), "forma_pagamento": data.payment_method.value, "vencimento": datetime.combine(data.due_date, time.min, tzinfo=timezone.utc) if data.due_date else None, "prazos_dias": data.installment_days, "observacoes": data.notes, "status": PurchaseStatus.PENDING.value, "usuario_id": user.id, "usuario": user.username, "data_hora": now, "recebido_em": None, "cancelado_em": None, "motivo_cancelamento": None, "pdf_path": None}
        result = self._purchases.insert_one(document); document["_id"] = result.inserted_id; return self._to_model(document)

    def mark_received(self, purchase_id: str) -> Purchase:
        item = self._purchases.find_one_and_update({"_id": _id(purchase_id), "status": {"$in": [PurchaseStatus.PENDING.value, PurchaseStatus.SENT.value, PurchaseStatus.RECEIPT_CONFIRMED.value]}}, {"$set": {"status": PurchaseStatus.RECEIVED.value, "recebido_em": utc_now()}}, return_document=ReturnDocument.AFTER)
        if item is None: raise ValueError("Compra não está aguardando recebimento.")
        return self._to_model(item)

    def mark_failed(self, purchase_id: str) -> None: self._purchases.update_one({"_id": _id(purchase_id), "status": PurchaseStatus.PENDING.value}, {"$set": {"status": PurchaseStatus.FAILED.value}})

    def mark_sent(self, purchase_id: str, pdf_path: str) -> Purchase:
        item = self._purchases.find_one_and_update({"_id": _id(purchase_id), "status": PurchaseStatus.PENDING.value}, {"$set": {"status": PurchaseStatus.SENT.value, "pdf_path": pdf_path}}, return_document=ReturnDocument.AFTER)
        if item is None: raise ValueError("Pedido não está pendente para envio.")
        return self._to_model(item)

    def confirm_receipt(self, purchase_id: str, invoice_numbers: list[str]) -> Purchase:
        joined = ", ".join(invoice_numbers)
        item = self._purchases.find_one_and_update(
            {"_id": _id(purchase_id), "status": {"$in": [PurchaseStatus.PENDING.value, PurchaseStatus.SENT.value]}},
            {"$set": {"numeros_notas": invoice_numbers, "numero_nota": joined, "status": PurchaseStatus.RECEIPT_CONFIRMED.value, "recebimento_confirmado_em": utc_now()}},
            return_document=ReturnDocument.AFTER,
        )
        if item is None: raise ValueError("Pedido não está aguardando recebimento.")
        return self._to_model(item)

    def invoice_conflicts(self, supplier_id: str, invoice_numbers: list[str], exclude_purchase_id: str) -> list[tuple[str, str]]:
        """Retorna (NF-e, pedido) já utilizados pelo mesmo fornecedor."""
        requested = {number.strip().casefold(): number.strip() for number in invoice_numbers}
        conflicts: list[tuple[str, str]] = []
        query = {"fornecedor_id": supplier_id, "_id": {"$ne": _id(exclude_purchase_id)}}
        for document in self._purchases.find(query, {"numero": 1, "numero_nota": 1, "numeros_notas": 1}):
            stored = document.get("numeros_notas") or []
            if not stored and document.get("numero_nota"): stored = [part.strip() for part in document["numero_nota"].split(",")]
            for number in stored:
                key = str(number).strip().casefold()
                if key in requested: conflicts.append((requested[key], document.get("numero", "pedido anterior")))
        return conflicts

    def cancel(self, purchase_id: str, reason: str) -> Purchase:
        item = self._purchases.find_one_and_update({"_id": _id(purchase_id), "status": PurchaseStatus.RECEIVED.value}, {"$set": {"status": PurchaseStatus.CANCELLED.value, "cancelado_em": utc_now(), "motivo_cancelamento": reason}}, return_document=ReturnDocument.AFTER)
        if item is None: raise ValueError("Somente compra recebida pode ser cancelada.")
        self._payables.update_many({"compra_id": purchase_id, "status": {"$ne": "paga"}}, {"$set": {"status": "cancelada", "atualizado_em": utc_now()}})
        return self._to_model(item)

    def create_payable(self, purchase: Purchase) -> None:
        due_dates = []
        if purchase.payment_method.value == "a_prazo": due_dates = [purchase.created_at.date() + timedelta(days=days) for days in purchase.installment_days]
        elif purchase.due_date is not None: due_dates = [purchase.due_date]
        if not due_dates: return
        base = (purchase.total / len(due_dates)).quantize(Decimal("0.01")); allocated = Decimal("0")
        documents = []
        for index, due_date in enumerate(due_dates, 1):
            value = purchase.total - allocated if index == len(due_dates) else base; allocated += value
            documents.append({"compra_id": purchase.id, "parcela": index, "total_parcelas": len(due_dates), "descricao": f"Compra {purchase.number} — {purchase.supplier_name} ({index}/{len(due_dates)})", "fornecedor_id": purchase.supplier_id, "valor_original": Decimal128(value), "valor_pago": Decimal128(Decimal("0")), "vencimento": datetime.combine(due_date, time.min, tzinfo=timezone.utc), "status": "aberta", "criado_em": utc_now(), "atualizado_em": utc_now()})
        self._payables.insert_many(documents)

    def cancel_payable(self, purchase_id: str) -> None:
        self._payables.update_many({"compra_id": purchase_id, "status": {"$ne": "paga"}}, {"$set": {"status": "cancelada", "atualizado_em": utc_now()}})

    def get(self, purchase_id: str) -> Purchase | None:
        item = self._purchases.find_one({"_id": _id(purchase_id)}); return self._to_model(item) if item else None

    def get_by_number(self, number: str) -> Purchase | None:
        item = self._purchases.find_one({"numero": number.strip().upper()}); return self._to_model(item) if item else None

    def set_expiration_dates(self, purchase_id: str, expiration_dates: dict[str, object]) -> Purchase:
        for product_id, expiration_date in expiration_dates.items():
            expiry = datetime.combine(expiration_date, time.min, tzinfo=timezone.utc)
            self._purchases.update_one({"_id": _id(purchase_id), "status": PurchaseStatus.RECEIPT_CONFIRMED.value}, {"$set": {"itens.$[item].data_validade": expiry}}, array_filters=[{"item.produto_id": product_id}])
        item = self._purchases.find_one({"_id": _id(purchase_id)})
        if item is None: raise ValueError("Pedido não encontrado.")
        return self._to_model(item)

    def list_page(self, *, status: str | None = None, page: int = 1, page_size: int = 50) -> tuple[list[Purchase], int]:
        query = {} if status is None else {"status": status}; total = self._purchases.count_documents(query); cursor = self._purchases.find(query).sort("data_hora", -1).skip((page - 1) * page_size).limit(page_size); return [self._to_model(item) for item in cursor], total

    @staticmethod
    def _to_model(item: dict[str, Any]) -> Purchase:
        items = []
        for value in item["itens"]:
            expiry = value.get("data_validade"); expiry_date = expiry.date() if isinstance(expiry, datetime) else expiry
            items.append(PurchaseItem(product_id=value["produto_id"], product_name=value["produto_nome"], package_type=value["tipo_embalagem"], quantity=value["quantidade"], units_per_pack=value.get("unidades_por_fardo"), cost_per_package=_decimal(value["custo_embalagem"]), lot_code=value.get("lote"), expiration_date=expiry_date))
        due = item.get("vencimento"); due_date = due.date() if isinstance(due, datetime) else due
        invoice_numbers = item.get("numeros_notas") or ([item["numero_nota"]] if item.get("numero_nota") else [])
        return Purchase(id=str(item["_id"]), number=item["numero"], supplier_id=item["fornecedor_id"], supplier_name=item["fornecedor_nome"], supplier_whatsapp=item.get("fornecedor_whatsapp"), invoice_number=item.get("numero_nota"), invoice_numbers=invoice_numbers, items=items, discount=_decimal(item.get("desconto")), freight=_decimal(item.get("frete")), payment_method=item["forma_pagamento"], due_date=due_date, installment_days=item.get("prazos_dias", []), notes=item.get("observacoes"), status=item["status"], created_by=item.get("usuario") or "", created_at=item["data_hora"], received_at=item.get("recebido_em"), cancelled_at=item.get("cancelado_em"), cancellation_reason=item.get("motivo_cancelamento"), pdf_path=item.get("pdf_path"))
