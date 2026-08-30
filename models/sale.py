"""Modelos do PDV varejista e seus pagamentos."""
from datetime import date,datetime
from decimal import Decimal
from enum import StrEnum
from pydantic import BaseModel, Field, model_validator
from models.auth import utc_now
from models.catalog import PackageType

class PaymentMethod(StrEnum):
    CASH = "dinheiro"; PIX = "pix"; DEBIT = "debito"; CREDIT = "credito"; INSTALLMENT_CREDIT = "credito_parcelado"; STORE_CREDIT = "fiado"

class SaleStatus(StrEnum):
    PENDING = "processando"; COMPLETED = "concluida"; CANCELLED = "cancelada"; FAILED = "falha"

class SaleItem(BaseModel):
    product_id: str; product_name: str; package_type: PackageType; quantity: int = Field(gt=0, le=1_000_000); units_per_pack: int | None = None
    unit_price: Decimal = Field(gt=0, max_digits=14, decimal_places=2); discount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    @property
    def converted_units(self) -> int: return self.quantity * self.units_per_pack if self.package_type == PackageType.PACK and self.units_per_pack else self.quantity
    @property
    def subtotal(self) -> Decimal: return (self.unit_price * self.quantity).quantize(Decimal("0.01"))
    @property
    def total(self) -> Decimal: return (self.subtotal - self.discount).quantize(Decimal("0.01"))
    @model_validator(mode="after")
    def validate_item(self):
        if self.package_type == PackageType.PACK and not self.units_per_pack: raise ValueError("produto sem composição de fardo")
        if self.discount > self.subtotal: raise ValueError("desconto do item supera o subtotal")
        return self

class SalePayment(BaseModel):
    method: PaymentMethod; amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2); installments: int = Field(default=1, ge=1, le=24)

class SaleInput(BaseModel):
    command_id: str | None = None; customer_id: str | None = None; customer_name: str | None = None; items: list[SaleItem] = Field(min_length=1, max_length=500)
    total_discount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2); surcharge: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2); delivery_fee: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2); notes: str | None = Field(default=None, max_length=1000); payments: list[SalePayment] = Field(min_length=1, max_length=10)
    credit_due_date:date|None=None; credit_allow_overdue:bool=False; credit_allow_over_limit:bool=False; credit_justification:str|None=Field(default=None,max_length=500)
    @property
    def subtotal(self): return sum((item.total for item in self.items), Decimal("0"))
    @property
    def total(self): return (self.subtotal - self.total_discount + self.surcharge + self.delivery_fee).quantize(Decimal("0.01"))
    @property
    def paid(self): return sum((payment.amount for payment in self.payments), Decimal("0"))
    @property
    def change(self): return (self.paid - self.total).quantize(Decimal("0.01"))
    @model_validator(mode="after")
    def validate_totals(self):
        if self.total_discount > self.subtotal: raise ValueError("desconto total supera o subtotal")
        if self.total <= 0: raise ValueError("total da venda deve ser positivo")
        if self.paid < self.total: raise ValueError("pagamentos não cobrem o total")
        if self.paid > self.total and not any(p.method == PaymentMethod.CASH for p in self.payments): raise ValueError("troco somente é permitido em dinheiro")
        if any(p.method==PaymentMethod.STORE_CREDIT for p in self.payments) and (not self.customer_id or not self.credit_due_date):raise ValueError("Venda fiada exige cliente e vencimento.")
        return self

class Sale(SaleInput):
    id: str | None = None; number: str; status: SaleStatus; created_by: str; created_at: datetime = Field(default_factory=utc_now); completed_at: datetime | None = None
