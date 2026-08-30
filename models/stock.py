"""Modelos de estoque, lotes e inventário."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from models.auth import utc_now
from models.catalog import PackageType


class StockMovementType(StrEnum):
    PURCHASE_ENTRY = "entrada_compra"
    SALE_EXIT = "saida_venda"
    RETURN_ENTRY = "devolucao"
    EXCHANGE_ENTRY = "troca_entrada"
    EXCHANGE_EXIT = "troca_saida"
    LOSS = "perda"
    DAMAGE = "avaria"
    EXPIRATION = "vencimento"
    INTERNAL_USE = "uso_interno"
    BONUS = "bonificacao"
    INVENTORY = "inventario"
    MANUAL_ADJUSTMENT = "ajuste_manual"
    COMMAND_RESERVATION = "reserva_comanda"
    RESERVATION_RELEASE = "liberacao_reserva"
    CANCELLATION_RELEASE = "liberacao_cancelamento"


ENTRY_TYPES = {StockMovementType.PURCHASE_ENTRY, StockMovementType.RETURN_ENTRY, StockMovementType.EXCHANGE_ENTRY, StockMovementType.BONUS}
EXIT_TYPES = {StockMovementType.SALE_EXIT, StockMovementType.EXCHANGE_EXIT, StockMovementType.LOSS, StockMovementType.DAMAGE, StockMovementType.EXPIRATION, StockMovementType.INTERNAL_USE}


class StockMovementRequest(BaseModel):
    product_id: str
    product_name: str
    movement_type: StockMovementType
    package_type: PackageType = PackageType.UNIT
    informed_quantity: int = Field(gt=0, le=1_000_000_000)
    units_per_pack: int | None = Field(default=None, ge=2, le=1000)
    reason: str = Field(min_length=3, max_length=500)
    related_document: str | None = Field(default=None, max_length=100)
    lot_code: str | None = Field(default=None, max_length=60)
    expiration_date: date | None = None
    adjustment_direction: Literal["entrada", "saida"] | None = None

    @model_validator(mode="after")
    def validate_package(self) -> "StockMovementRequest":
        if self.package_type == PackageType.PACK and not self.units_per_pack:
            raise ValueError("produto sem composição de fardo")
        if self.movement_type == StockMovementType.MANUAL_ADJUSTMENT and self.adjustment_direction is None:
            raise ValueError("informe a direção do ajuste manual")
        return self

    @property
    def converted_units(self) -> int:
        return self.informed_quantity * self.units_per_pack if self.package_type == PackageType.PACK and self.units_per_pack else self.informed_quantity


class InventoryRequest(BaseModel):
    product_id: str
    product_name: str
    counted_units: int = Field(ge=0, le=2_000_000_000)
    reason: str = Field(min_length=3, max_length=500)


class StockMovement(BaseModel):
    id: str | None = None
    product_id: str
    product_name: str
    movement_type: StockMovementType
    package_type: PackageType
    informed_quantity: int
    converted_units: int
    balance_before: int
    balance_after: int
    reason: str
    user_id: str
    username: str
    occurred_at: datetime = Field(default_factory=utc_now)
    related_document: str | None = None
    lot_code: str | None = None


class StockLot(BaseModel):
    id: str | None = None
    product_id: str
    product_name: str
    code: str
    quantity_units: int = Field(ge=0)
    expiration_date: date | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
