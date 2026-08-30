"""Modelos validados do cadastro de fornecedores."""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from models.auth import utc_now
from models.customer import Address, only_digits, valid_cpf


def valid_cnpj(value: str) -> bool:
    digits = only_digits(value) or ""
    if len(digits) != 14 or digits == digits[0] * 14:
        return False
    for size in (12, 13):
        weights = list(range(size - 7, 1, -1)) + list(range(9, 1, -1))
        total = sum(int(digit) * weight for digit, weight in zip(digits[:size], weights, strict=True))
        check = 0 if total % 11 < 2 else 11 - total % 11
        if check != int(digits[size]):
            return False
    return True


class SupplierInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    legal_name: str = Field(min_length=2, max_length=150)
    trade_name: str | None = Field(default=None, max_length=150)
    document: str = Field(min_length=11, max_length=18)
    state_registration: str | None = Field(default=None, max_length=30)
    phone: str | None = Field(default=None, max_length=15)
    whatsapp: str | None = Field(default=None, max_length=15)
    email: str | None = Field(default=None, max_length=254)
    address: Address | None = None
    commercial_contact: str | None = Field(default=None, max_length=100)
    delivery_term: str | None = Field(default=None, max_length=100)
    payment_terms: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=1000)
    active: bool = True

    @field_validator("document")
    @classmethod
    def validate_document(cls, value: str) -> str:
        digits = only_digits(value) or ""
        if not ((len(digits) == 11 and valid_cpf(digits)) or (len(digits) == 14 and valid_cnpj(digits))):
            raise ValueError("CPF ou CNPJ inválido")
        return digits

    @field_validator("phone", "whatsapp")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        digits = only_digits(value)
        if digits and len(digits) not in (10, 11):
            raise ValueError("telefone deve possuir 10 ou 11 dígitos")
        return digits

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if not value: return None
        value = value.lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("e-mail inválido")
        return value


class Supplier(SupplierInput):
    id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    purchase_count: int = 0
    total_purchased: Decimal = Decimal("0")
    last_purchase_at: datetime | None = None


class SupplierPage(BaseModel):
    items: list[Supplier]
    total: int
    page: int
    page_size: int

