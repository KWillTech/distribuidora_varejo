"""Modelos financeiros com valores decimais."""
from datetime import date,datetime
from decimal import Decimal
from enum import StrEnum
from pydantic import BaseModel,Field,model_validator
from models.auth import utc_now

class FinancialKind(StrEnum): PAYABLE="conta_pagar"; RECEIVABLE="conta_receber"; EXPENSE="despesa"; REVENUE="receita"
class FinancialStatus(StrEnum): OPEN="aberta"; PARTIAL="parcial"; PAID="paga"; CANCELLED="cancelada"
class FinancialInput(BaseModel):
    kind:FinancialKind; description:str=Field(min_length=2,max_length=300); category:str=Field(min_length=2,max_length=100); amount:Decimal=Field(gt=0,max_digits=14,decimal_places=2); due_date:date; notes:str|None=Field(default=None,max_length=1000); recurring:bool=False; recurrence_count:int=Field(default=1,ge=1,le=60)
    @model_validator(mode="after")
    def validate_recurrence(self):
        if not self.recurring:self.recurrence_count=1
        return self
class FinancialEntry(BaseModel):
    id:str; kind:FinancialKind; description:str; category:str="Outros"; original_amount:Decimal; paid_amount:Decimal=Decimal("0"); due_date:date; status:FinancialStatus=FinancialStatus.OPEN; notes:str|None=None; created_at:datetime=Field(default_factory=utc_now)
    @property
    def balance(self):return (self.original_amount-self.paid_amount).quantize(Decimal("0.01"))
class PaymentInput(BaseModel):
    amount:Decimal=Field(gt=0,max_digits=14,decimal_places=2); payment_date:date; payment_method:str=Field(min_length=2,max_length=50); notes:str|None=Field(default=None,max_length=500)
