"""Modelos de abertura, movimentação e fechamento de caixa."""
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from pydantic import BaseModel,Field,model_validator
from models.auth import utc_now

class CashStatus(StrEnum): OPEN="aberto"; CLOSED="fechado"
class CashMovementType(StrEnum): OPENING="abertura"; SALE="venda"; CREDIT_RECEIPT="recebimento_fiado"; SUPPLY="suprimento"; WITHDRAWAL="sangria"; REVERSAL="estorno"

class CashRegister(BaseModel):
    id:str|None=None; user_id:str; username:str; opening_amount:Decimal=Field(ge=0,max_digits=14,decimal_places=2); expected_amount:Decimal=Field(default=Decimal("0"),max_digits=14,decimal_places=2); counted_amount:Decimal|None=None; difference:Decimal|None=None; justification:str|None=None; status:CashStatus=CashStatus.OPEN; opened_at:datetime=Field(default_factory=utc_now); closed_at:datetime|None=None

class CashMovementInput(BaseModel):
    movement_type:CashMovementType; amount:Decimal=Field(gt=0,max_digits=14,decimal_places=2); payment_method:str="dinheiro"; reason:str|None=Field(default=None,max_length=500); related_document:str|None=None

class CashCloseInput(BaseModel):
    counted_amount:Decimal=Field(ge=0,max_digits=14,decimal_places=2); justification:str|None=Field(default=None,max_length=500)
    @model_validator(mode="after")
    def validate_justification(self):
        return self
