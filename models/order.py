"""Modelos de pedidos varejistas e entregas."""
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from pydantic import BaseModel, Field,field_validator
from models.auth import utc_now

class OrderStatus(StrEnum):
    AWAITING_PAYMENT="aguardando_pagamento"; PAID="pago"; SEPARATING="em_separacao"; READY_PICKUP="pronto_retirada"; READY_DELIVERY="pronto_entrega"; OUT_FOR_DELIVERY="saiu_entrega"; DELIVERED="entregue"; NOT_DELIVERED="nao_entregue"; CANCELLED="cancelado"

STATUS_LABELS={OrderStatus.AWAITING_PAYMENT:"Aguardando pagamento",OrderStatus.PAID:"Pago",OrderStatus.SEPARATING:"Em separação",OrderStatus.READY_PICKUP:"Pronto para retirada",OrderStatus.READY_DELIVERY:"Pronto para entrega",OrderStatus.OUT_FOR_DELIVERY:"Saiu para entrega",OrderStatus.DELIVERED:"Entregue",OrderStatus.NOT_DELIVERED:"Não entregue",OrderStatus.CANCELLED:"Cancelado"}

class OrderInput(BaseModel):
    customer_name:str=Field(min_length=2,max_length=120); phone:str=Field(min_length=8,max_length=30); address:str=Field(min_length=5,max_length=300); reference:str|None=Field(default=None,max_length=200); products:str=Field(min_length=2,max_length=2000); volumes:int=Field(gt=0,le=10000); delivery_fee:Decimal=Field(default=Decimal("0"),ge=0,max_digits=14,decimal_places=2); payment_method:str=Field(min_length=2,max_length=50); change_for:Decimal|None=Field(default=None,ge=0,max_digits=14,decimal_places=2); notes:str|None=Field(default=None,max_length=1000)
    @field_validator("phone")
    @classmethod
    def validate_phone(cls,value):
        digits="".join(character for character in value if character.isdigit())
        if len(digits) not in (10,11):raise ValueError("telefone deve possuir 10 ou 11 dígitos")
        return digits

class Order(OrderInput):
    id:str|None=None; number:str; status:OrderStatus=OrderStatus.AWAITING_PAYMENT; delivery_person_id:str|None=None; delivery_person_name:str|None=None; occurrences:list[str]=Field(default_factory=list); created_by:str; created_at:datetime=Field(default_factory=utc_now); departed_at:datetime|None=None; delivered_at:datetime|None=None
