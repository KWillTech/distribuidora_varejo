"""Modelos de compras e recebimento de mercadorias."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from models.auth import utc_now
from models.catalog import PackageType


class PurchaseStatus(StrEnum):
    PENDING = "aguardando_recebimento"
    SENT = "pedido_enviado"
    RECEIPT_CONFIRMED = "recebimento_confirmado"
    RECEIVED = "recebida"
    CANCELLED = "cancelada"
    FAILED = "falha_recebimento"


class PurchasePaymentMethod(StrEnum):
    CASH = "dinheiro"
    PIX = "pix"
    BOLETO = "boleto"
    CREDIT = "a_prazo"


class PurchaseItem(BaseModel):
    product_id: str
    product_name: str
    package_type: PackageType
    quantity: int = Field(gt=0, le=1_000_000)
    units_per_pack: int | None = Field(default=None, ge=2, le=1000)
    cost_per_package: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    lot_code: str | None = Field(default=None, max_length=60)
    expiration_date: date | None = None

    @model_validator(mode="after")
    def validate_pack(self) -> "PurchaseItem":
        if self.package_type == PackageType.PACK and not self.units_per_pack:
            raise ValueError("produto sem quantidade por fardo")
        return self

    @property
    def converted_units(self) -> int:
        return self.quantity * self.units_per_pack if self.package_type == PackageType.PACK and self.units_per_pack else self.quantity

    @property
    def unit_cost(self) -> Decimal:
        divisor = self.units_per_pack if self.package_type == PackageType.PACK and self.units_per_pack else 1
        return (self.cost_per_package / divisor).quantize(Decimal("0.01"))

    @property
    def total(self) -> Decimal:
        return (self.cost_per_package * self.quantity).quantize(Decimal("0.01"))


class PurchaseInput(BaseModel):
    supplier_id: str
    supplier_name: str
    supplier_whatsapp: str | None = None
    invoice_number: str | None = Field(default=None, max_length=2500)
    items: list[PurchaseItem] = Field(min_length=1, max_length=500)
    discount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    freight: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    payment_method: PurchasePaymentMethod
    due_date: date | None = None
    installment_days: list[int] = Field(default_factory=list, max_length=24)
    notes: str | None = Field(default=None, max_length=1000)

    @property
    def subtotal(self) -> Decimal: return sum((item.total for item in self.items), Decimal("0.00"))
    @property
    def total(self) -> Decimal: return (self.subtotal - self.discount + self.freight).quantize(Decimal("0.01"))

    @model_validator(mode="after")
    def validate_totals(self) -> "PurchaseInput":
        if self.discount > self.subtotal: raise ValueError("desconto não pode superar o subtotal")
        if self.payment_method == PurchasePaymentMethod.BOLETO and self.due_date is None:
            raise ValueError("informe o vencimento do boleto")
        if self.payment_method == PurchasePaymentMethod.CREDIT:
            if not self.installment_days: raise ValueError("informe os prazos, por exemplo 7/14/21")
            if any(day <= 0 or day > 3650 for day in self.installment_days) or self.installment_days != sorted(set(self.installment_days)):
                raise ValueError("prazos devem ser dias positivos, únicos e crescentes")
        return self


class Purchase(PurchaseInput):
    id: str | None = None
    number: str
    status: PurchaseStatus = PurchaseStatus.PENDING
    created_by: str
    created_at: datetime = Field(default_factory=utc_now)
    received_at: datetime | None = None
    cancelled_at: datetime | None = None
    cancellation_reason: str | None = None
    pdf_path: str | None = None
    invoice_numbers: list[str] = Field(default_factory=list)
