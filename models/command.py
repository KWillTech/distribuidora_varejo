"""Domínio de comandas e reservas de consumo."""
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from pydantic import BaseModel,ConfigDict,Field,model_validator
from models.auth import utc_now
from models.catalog import PackageType

class CommandStatus(StrEnum):
    OPEN="aberta"; SERVING="em_atendimento"; AWAITING_PAYMENT="aguardando_pagamento"; FINALIZED="finalizada"; CANCELLED="cancelada"; MERGED="unificada"
class ServiceType(StrEnum): COUNTER="balcao"; PICKUP="retirada"; DELIVERY="entrega"
class CommandOpenInput(BaseModel):
    model_config=ConfigDict(str_strip_whitespace=True)
    slot_number:int|None=Field(default=None,ge=1,le=30); customer_id:str|None=None; customer_name:str|None=None; identification:str|None=Field(default=None,max_length=120); phone:str|None=Field(default=None,max_length=30); people:int|None=Field(default=None,ge=1,le=1000); service_type:ServiceType=ServiceType.COUNTER; notes:str|None=Field(default=None,max_length=1000); confirm_duplicate:bool=False
    @model_validator(mode="after")
    def identity(self):
        if not self.customer_id and not (self.identification or "").strip():raise ValueError("Informe um cliente ou uma identificação para a comanda.")
        return self
class CommandItemInput(BaseModel):
    product_id:str; code:str; product_name:str; package_type:PackageType; quantity:int=Field(gt=0,le=100000); units_per_pack:int|None=None; price:Decimal=Field(gt=0,max_digits=14,decimal_places=2); discount:Decimal=Field(default=Decimal("0"),ge=0); barcode:str|None=None; notes:str|None=Field(default=None,max_length=300)
    @property
    def base_units(self):return self.quantity*(self.units_per_pack or 0) if self.package_type==PackageType.PACK else self.quantity
    @property
    def subtotal(self):return (self.price*self.quantity-self.discount).quantize(Decimal("0.01"))
    @model_validator(mode="after")
    def pack(self):
        if self.package_type==PackageType.PACK and not self.units_per_pack:raise ValueError("Produto sem configuração de fardo.")
        if self.discount>self.price*self.quantity:raise ValueError("Desconto supera o subtotal.")
        return self
class CommandItem(CommandItemInput):item_id:str; user_id:str|None=None; username:str=""; added_at:datetime=Field(default_factory=utc_now)
class Command(BaseModel):
    id:str|None=None; number:str; slot_number:int|None=None; customer_id:str|None=None; customer_name:str|None=None; identification:str; phone:str|None=None; people:int|None=None; service_type:ServiceType; opened_by_id:str|None=None; opened_by:str; opened_at:datetime; closed_at:datetime|None=None; status:CommandStatus; items:list[CommandItem]=Field(default_factory=list); discount:Decimal=Decimal("0"); surcharge:Decimal=Decimal("0"); delivery_fee:Decimal=Decimal("0"); payments:list[dict]=Field(default_factory=list); sale_id:str|None=None; notes:str|None=None; version:int=1
    @property
    def subtotal(self):return sum((x.subtotal for x in self.items),Decimal("0"))
    @property
    def total(self):return (self.subtotal-self.discount+self.surcharge+self.delivery_fee).quantize(Decimal("0.01"))
class CommandSummary(BaseModel):
    open:int=0; serving:int=0; awaiting:int=0; finalized_today:int=0; open_value:Decimal=Decimal("0"); average_minutes:Decimal=Decimal("0")
