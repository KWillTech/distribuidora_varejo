"""Operações atômicas de estoque e persistência de lotes."""

from __future__ import annotations

from datetime import datetime, time, timezone
from typing import Any

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.database import Database
from pymongo.errors import PyMongoError

from models.auth import User, utc_now
from models.catalog import PackageType
from models.stock import ENTRY_TYPES, EXIT_TYPES, InventoryRequest, StockLot, StockMovement, StockMovementRequest, StockMovementType


class StockConflictError(RuntimeError):
    """Saldo foi alterado ou é insuficiente para a operação."""


def _id(value: str) -> ObjectId | str:
    return ObjectId(value) if ObjectId.is_valid(value) else value


class StockRepository:
    def __init__(self, database: Database) -> None:
        self._products = database["produtos"]; self._movements = database["movimentacoes_estoque"]; self._lots = database["lotes"]

    def apply(self, request: StockMovementRequest, user: User, allow_negative: bool = False) -> StockMovement:
        units = request.converted_units
        if request.movement_type in ENTRY_TYPES: delta = units
        elif request.movement_type in EXIT_TYPES: delta = -units
        elif request.movement_type == StockMovementType.MANUAL_ADJUSTMENT: delta = units if request.adjustment_direction == "entrada" else -units
        else: raise ValueError("Use o fluxo de inventário para este tipo de movimentação.")
        lot_changed = False
        if delta < 0 and request.lot_code:
            lot_query: dict[str, Any] = {"produto_id": request.product_id, "codigo": request.lot_code}
            if not allow_negative: lot_query["quantidade_unidades"] = {"$gte": units}
            lot = self._lots.find_one_and_update(lot_query, {"$inc": {"quantidade_unidades": delta}, "$set": {"atualizado_em": utc_now()}}, return_document=ReturnDocument.BEFORE)
            if lot is None: raise StockConflictError("Lote inexistente ou com saldo insuficiente.")
            lot_changed = True
        query: dict[str, Any] = {"_id": _id(request.product_id), "ativo": True}
        if delta < 0 and not allow_negative: query["estoque_atual_unidades"] = {"$gte": units}
        before = self._products.find_one_and_update(query, {"$inc": {"estoque_atual_unidades": delta}, "$set": {"atualizado_em": utc_now()}}, return_document=ReturnDocument.BEFORE)
        if before is None:
            if lot_changed: self._lots.update_one({"produto_id": request.product_id, "codigo": request.lot_code}, {"$inc": {"quantidade_unidades": -delta}})
            raise StockConflictError("Produto inativo, inexistente ou com estoque insuficiente.")
        balance_before = int(before.get("estoque_atual_unidades", 0)); balance_after = balance_before + delta
        try:
            if delta > 0 and request.lot_code:
                expiry = datetime.combine(request.expiration_date, time.min, tzinfo=timezone.utc) if request.expiration_date else None
                self._lots.update_one({"produto_id": request.product_id, "codigo": request.lot_code}, {"$setOnInsert": {"produto_nome": request.product_name, "criado_em": utc_now()}, "$set": {"data_validade": expiry, "atualizado_em": utc_now()}, "$inc": {"quantidade_unidades": delta}}, upsert=True)
                lot_changed = True
            document = {"produto_id": request.product_id, "produto_nome": request.product_name, "tipo_movimentacao": request.movement_type.value, "tipo_embalagem": request.package_type.value, "quantidade_informada": request.informed_quantity, "quantidade_convertida_unidades": units, "saldo_anterior": balance_before, "saldo_final": balance_after, "motivo": request.reason, "usuario_id": user.id, "usuario": user.username, "data_hora": utc_now(), "documento_relacionado": request.related_document, "lote": request.lot_code}
            result = self._movements.insert_one(document); document["_id"] = result.inserted_id
            return self._to_movement(document)
        except (PyMongoError, OSError, ValueError):
            self._products.update_one({"_id": _id(request.product_id)}, {"$inc": {"estoque_atual_unidades": -delta}})
            if lot_changed and request.lot_code: self._lots.update_one({"produto_id": request.product_id, "codigo": request.lot_code}, {"$inc": {"quantidade_unidades": -delta}})
            raise

    def inventory(self, request: InventoryRequest, user: User) -> StockMovement:
        before = self._products.find_one_and_update({"_id": _id(request.product_id), "ativo": True}, {"$set": {"estoque_atual_unidades": request.counted_units, "atualizado_em": utc_now()}}, return_document=ReturnDocument.BEFORE)
        if before is None: raise StockConflictError("Produto inativo ou inexistente.")
        previous = int(before.get("estoque_atual_unidades", 0)); delta = request.counted_units - previous
        document = {"produto_id": request.product_id, "produto_nome": request.product_name, "tipo_movimentacao": StockMovementType.INVENTORY.value, "tipo_embalagem": PackageType.UNIT.value, "quantidade_informada": abs(delta), "quantidade_convertida_unidades": delta, "saldo_anterior": previous, "saldo_final": request.counted_units, "motivo": request.reason, "usuario_id": user.id, "usuario": user.username, "data_hora": utc_now(), "documento_relacionado": None, "lote": None}
        try: result = self._movements.insert_one(document); document["_id"] = result.inserted_id
        except PyMongoError:
            self._products.update_one({"_id": _id(request.product_id), "estoque_atual_unidades": request.counted_units}, {"$set": {"estoque_atual_unidades": previous}}); raise
        return self._to_movement(document)

    def list_movements(self, *, product_id: str | None = None, movement_type: str | None = None, page: int = 1, page_size: int = 50) -> tuple[list[StockMovement], int]:
        query: dict[str, Any] = {}
        if product_id: query["produto_id"] = product_id
        if movement_type: query["tipo_movimentacao"] = movement_type
        total = self._movements.count_documents(query); cursor = self._movements.find(query).sort("data_hora", -1).skip((page - 1) * page_size).limit(page_size)
        return [self._to_movement(item) for item in cursor], total

    def list_lots(self, product_id: str | None = None, expiring_until: datetime | None = None) -> list[StockLot]:
        query: dict[str, Any] = {"quantidade_unidades": {"$gt": 0}}
        if product_id: query["produto_id"] = product_id
        if expiring_until: query["data_validade"] = {"$ne": None, "$lte": expiring_until}
        return [self._to_lot(item) for item in self._lots.find(query).sort("data_validade", 1)]

    @staticmethod
    def _to_movement(item: dict[str, Any]) -> StockMovement:
        # Reservas de comandas não alteram o estoque físico; por isso não possuem
        # saldo anterior/final. Mantemos ambos iguais ao saldo informado (ou zero)
        # para que o histórico legado e as novas reservas possam coexistir.
        balance_before = int(item.get("saldo_anterior", item.get("saldo_fisico", 0)) or 0)
        balance_after = int(item.get("saldo_final", balance_before) or balance_before)
        return StockMovement(id=str(item["_id"]), product_id=item["produto_id"], product_name=item["produto_nome"], movement_type=item["tipo_movimentacao"], package_type=item.get("tipo_embalagem", "unidade"), informed_quantity=abs(int(item.get("quantidade_informada", item.get("quantidade_convertida_unidades", 0)) or 0)), converted_units=int(item.get("quantidade_convertida_unidades", 0) or 0), balance_before=balance_before, balance_after=balance_after, reason=item.get("motivo") or "Movimentação de reserva", user_id=item.get("usuario_id") or "", username=item.get("usuario") or "", occurred_at=item["data_hora"], related_document=item.get("documento_relacionado"), lot_code=item.get("lote"))

    @staticmethod
    def _to_lot(item: dict[str, Any]) -> StockLot:
        expiry = item.get("data_validade"); expiry_date = expiry.date() if isinstance(expiry, datetime) else expiry
        return StockLot(id=str(item["_id"]), product_id=item["produto_id"], product_name=item["produto_nome"], code=item["codigo"], quantity_units=item["quantidade_unidades"], expiration_date=expiry_date, created_at=item["criado_em"], updated_at=item["atualizado_em"])
