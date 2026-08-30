"""Domínio financeiro de vendas fiadas e contas de clientes."""
from datetime import date,datetime
from decimal import Decimal
from enum import StrEnum
from pydantic import BaseModel,Field,model_validator
from models.auth import utc_now

class CreditCustomerStatus(StrEnum): RELEASED="liberado"; NEAR_LIMIT="proximo_limite"; LIMIT_REACHED="limite_atingido"; OVERDUE="divida_vencida"; BLOCKED="bloqueado_manual"; INACTIVE="inativo"
class ReceivableStatus(StrEnum): PENDING="pendente"; PARTIAL="parcialmente_pago"; PAID="pago"; OVERDUE="vencido"; RENEGOTIATED="renegociado"; CANCELLED="cancelado"
class CreditMovementType(StrEnum): SALE="debito_venda"; PAYMENT="pagamento"; INTEREST="juros"; FINE="multa"; DISCOUNT="desconto"; REVERSAL="estorno"; CANCELLATION="cancelamento"; RENEGOTIATION="renegociacao"; RETURN_CREDIT="credito_devolucao"

class CreditProfile(BaseModel):
    enabled:bool=False; credit_limit:Decimal=Field(default=Decimal("0"),ge=0,max_digits=14,decimal_places=2); debt_balance:Decimal=Field(default=Decimal("0"),ge=0,max_digits=14,decimal_places=2); default_due_day:int|None=Field(default=None,ge=1,le=28); due_days:int=Field(default=30,ge=1,le=365); allow_overdue_purchase:bool=False; status:CreditCustomerStatus=CreditCustomerStatus.INACTIVE; block_reason:str|None=None; blocked_at:datetime|None=None; blocked_by:str|None=None; financial_notes:str|None=Field(default=None,max_length=1000); over_limit_amount:Decimal=Decimal("0")
    @property
    def available_limit(self):return max(Decimal("0"),self.credit_limit-self.debt_balance)

class CreditSaleAuthorization(BaseModel): due_date:date; allow_overdue:bool=False; allow_over_limit:bool=False; justification:str|None=Field(default=None,max_length=500)
class Receivable(BaseModel):
    id:str|None=None; sale_id:str; sale_number:str; customer_id:str; customer_name:str; original_amount:Decimal; paid_amount:Decimal=Decimal("0"); open_balance:Decimal; sale_date:datetime; due_date:date; last_payment_at:datetime|None=None; status:ReceivableStatus=ReceivableStatus.PENDING; notes:str|None=None; history:list[dict]=Field(default_factory=list)
class CreditPaymentInput(BaseModel):
    amount:Decimal=Field(gt=0,max_digits=14,decimal_places=2); payment_method:str=Field(min_length=2,max_length=50); notes:str|None=Field(default=None,max_length=500); account_ids:list[str]=Field(default_factory=list)
class CreditAdjustmentInput(BaseModel):
    amount:Decimal=Field(gt=0,max_digits=14,decimal_places=2); reason:str=Field(min_length=3,max_length=500)
class RenegotiationInput(BaseModel):
    account_ids:list[str]=Field(min_length=1); new_due_date:date; installments:int=Field(default=1,ge=1,le=36); interest:Decimal=Field(default=Decimal("0"),ge=0); discount:Decimal=Field(default=Decimal("0"),ge=0); down_payment:Decimal=Field(default=Decimal("0"),ge=0); justification:str=Field(min_length=3,max_length=500)
    @model_validator(mode="after")
    def totals(self):
        if self.interest and self.discount:raise ValueError("Informe juros ou desconto, não ambos.")
        return self
