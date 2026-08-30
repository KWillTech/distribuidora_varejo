"""Modelos de categorias e produtos do catálogo varejista."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from models.auth import utc_now


INITIAL_CATEGORIES = (
    "Cervejas", "Refrigerantes", "Águas", "Sucos", "Energéticos", "Isotônicos",
    "Destilados", "Vinhos", "Espumantes", "Gelo", "Carvão", "Copos e descartáveis",
    "Petiscos", "Combos", "Outros",
)


class PackageType(StrEnum):
    UNIT = "unidade"
    PACK = "fardo"


class CategoryInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(min_length=2, max_length=80)
    description: str | None = Field(default=None, max_length=300)
    active: bool = True


class Category(CategoryInput):
    id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ProductInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    internal_code: str = Field(min_length=1, max_length=40)
    unit_barcode: str | None = Field(default=None, max_length=32)
    pack_barcode: str | None = Field(default=None, max_length=32)
    name: str = Field(min_length=2, max_length=150)
    description: str | None = Field(default=None, max_length=1000)
    category_id: str
    category_name: str
    brand: str | None = Field(default=None, max_length=80)
    volume: str | None = Field(default=None, max_length=40)
    measurement_unit: str = Field(default="UN", min_length=1, max_length=20)
    package_description: str | None = Field(default=None, max_length=50)
    units_per_pack: int | None = Field(default=None, ge=2, le=1000)
    unit_cost: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    pack_cost: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    unit_price: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    pack_price: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    promotional_unit_price: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    promotional_pack_price: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    current_stock_units: int = Field(default=0, ge=0)
    minimum_stock: int = Field(default=0, ge=0)
    maximum_stock: int | None = Field(default=None, ge=0)
    storage_location: str | None = Field(default=None, max_length=80)
    main_supplier_id: str | None = None
    main_supplier_name: str | None = None
    initial_lot: str | None = Field(default=None, max_length=60)
    expiration_date: date | None = None
    photo_path: str | None = Field(default=None, max_length=500)
    active: bool = True

    @field_validator("internal_code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.upper()

    @field_validator("unit_barcode", "pack_barcode")
    @classmethod
    def validate_barcode(cls, value: str | None) -> str | None:
        if not value: return None
        if not value.isdigit() or len(value) not in range(8, 33):
            raise ValueError("código de barras deve conter entre 8 e 32 dígitos")
        return value

    @model_validator(mode="after")
    def validate_pack_and_stock(self) -> "ProductInput":
        pack_values = (self.pack_barcode, self.pack_cost, self.pack_price, self.promotional_pack_price)
        if any(value is not None for value in pack_values) and self.units_per_pack is None:
            raise ValueError("informe a quantidade de unidades por fardo")
        if self.maximum_stock is not None and self.maximum_stock < self.minimum_stock:
            raise ValueError("estoque máximo não pode ser menor que o mínimo")
        if self.unit_barcode and self.unit_barcode == self.pack_barcode:
            raise ValueError("os códigos de barras de unidade e fardo devem ser diferentes")
        return self

    @property
    def unit_margin_percent(self) -> Decimal:
        if self.unit_cost == 0: return Decimal("0")
        return ((self.unit_price - self.unit_cost) / self.unit_cost * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def calculated_pack_cost(self) -> Decimal | None:
        if self.units_per_pack is None: return None
        return self.pack_cost if self.pack_cost is not None else self.unit_cost * self.units_per_pack


class Product(ProductInput):
    id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @property
    def stock_display(self) -> str:
        if not self.units_per_pack: return f"{self.current_stock_units} un."
        packs, units = divmod(self.current_stock_units, self.units_per_pack)
        return f"{packs} fardo(s) e {units} un."


class ProductPage(BaseModel):
    items: list[Product]
    total: int
    page: int
    page_size: int
