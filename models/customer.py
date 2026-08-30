"""Modelos e validações do cadastro de clientes."""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from models.auth import utc_now
from models.credit import CreditProfile


def only_digits(value: str | None) -> str | None:
    if value is None:
        return None
    digits = re.sub(r"\D", "", value)
    return digits or None


def valid_cpf(value: str) -> bool:
    digits = only_digits(value) or ""
    if len(digits) != 11 or digits == digits[0] * 11:
        return False
    for size in (9, 10):
        total = sum(int(digits[index]) * (size + 1 - index) for index in range(size))
        check = (total * 10 % 11) % 10
        if check != int(digits[size]):
            return False
    return True


class Address(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    cep: str | None = None
    street: str = Field(min_length=2, max_length=120)
    number: str = Field(min_length=1, max_length=20)
    complement: str | None = Field(default=None, max_length=80)
    district: str = Field(min_length=2, max_length=80)
    city: str = Field(min_length=2, max_length=80)
    state: str = Field(min_length=2, max_length=2)
    reference: str | None = Field(default=None, max_length=200)
    label: str = Field(default="Principal", min_length=2, max_length=40)

    @field_validator("cep")
    @classmethod
    def validate_cep(cls, value: str | None) -> str | None:
        digits = only_digits(value)
        if digits and len(digits) != 8:
            raise ValueError("CEP deve possuir 8 dígitos")
        return digits

    @field_validator("state")
    @classmethod
    def normalize_state(cls, value: str) -> str:
        if not value.isalpha():
            raise ValueError("UF inválida")
        return value.upper()


class CustomerInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    full_name: str | None = Field(default=None, min_length=3, max_length=120)
    cpf: str | None = None
    birth_date: date | None = None
    phone: str | None = Field(default=None, max_length=15)
    whatsapp: str | None = Field(default=None, max_length=15)
    email: str | None = Field(default=None, max_length=254)
    main_address: Address | None = None
    additional_addresses: list[Address] = Field(default_factory=list, max_length=10)
    notes: str | None = Field(default=None, max_length=1000)
    age_confirmed: bool = False
    active: bool = True
    credit: CreditProfile = Field(default_factory=CreditProfile)

    @field_validator("full_name")
    @classmethod
    def normalize_optional_name(cls, value: str | None) -> str | None:
        return value or None

    @field_validator("cpf")
    @classmethod
    def validate_cpf(cls, value: str | None) -> str | None:
        digits = only_digits(value)
        if digits and not valid_cpf(digits):
            raise ValueError("CPF inválido")
        return digits

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        digits = only_digits(value)
        if digits and len(digits) not in (10, 11):
            raise ValueError("telefone deve possuir 10 ou 11 dígitos")
        return digits

    @field_validator("whatsapp")
    @classmethod
    def validate_whatsapp(cls, value: str | None) -> str | None:
        digits = only_digits(value)
        if digits and len(digits) not in (10, 11):
            raise ValueError("WhatsApp deve possuir 10 ou 11 dígitos")
        return digits

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if not value:
            return None
        value = value.lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("e-mail inválido")
        return value


class Customer(CustomerInput):
    id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    total_spent: Decimal = Decimal("0")
    average_ticket: Decimal = Decimal("0")
    last_purchase_at: datetime | None = None


class CustomerPage(BaseModel):
    items: list[Customer]
    total: int
    page: int
    page_size: int
