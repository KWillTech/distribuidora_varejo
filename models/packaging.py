"""Modelos das regras de venda por unidade e por fardo."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from models.catalog import PackageType, Product


class PackConfiguration(BaseModel):
    units_per_pack: int | None = Field(default=None, ge=2, le=1000)
    pack_barcode: str | None = Field(default=None, min_length=8, max_length=32, pattern=r"^\d+$")
    pack_price: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    promotional_pack_price: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)

    @model_validator(mode="after")
    def validate_complete_pack(self) -> "PackConfiguration":
        values = (self.pack_barcode, self.pack_price, self.promotional_pack_price)
        if self.units_per_pack is None and any(value is not None for value in values):
            raise ValueError("informe as unidades por fardo")
        if self.units_per_pack is not None and self.pack_price is None:
            raise ValueError("informe o preço de venda do fardo")
        return self


class SalePackageRequest(BaseModel):
    product: Product
    package_type: PackageType
    quantity: int = Field(gt=0, le=1_000_000)
    use_promotional_price: bool = True


class SalePackageQuote(BaseModel):
    product_id: str
    product_name: str
    package_type: PackageType
    informed_quantity: int
    converted_units: int
    unit_package_price: Decimal
    total: Decimal
    stock_before_units: int
    stock_after_units: int

