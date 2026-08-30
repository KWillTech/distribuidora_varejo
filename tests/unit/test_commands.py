from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path
import pytest
from models.auth import AuthenticatedSession,Permission,ProfileCode,User
from models.catalog import PackageType
from models.command import Command,CommandItem,CommandItemInput,CommandOpenInput,CommandStatus,ServiceType
from models.sale import PaymentMethod,SalePayment
from services.commands import CommandService

def actor(*permissions):
    user=User(id="u1",username="caixa",email="c@example.com",full_name="Pessoa Caixa",profile_code=ProfileCode.CASHIER)
    return AuthenticatedSession(session_id="s1",user=user,permissions=set(permissions))
class Audit:
    def __init__(self):self.rows=[]
    def record(self,**data):self.rows.append(data)
class Repo:
    def __init__(self):self.value=None; self.reserved=0
    def open(self,data,user):
        self.value=Command(id="c1",number="CMD-000001",customer_id=data.customer_id,customer_name=data.customer_name,identification=data.identification or data.customer_name,phone=data.phone,service_type=data.service_type,opened_by_id=user.id,opened_by=user.username,opened_at=datetime.now(timezone.utc),status=CommandStatus.OPEN); return self.value
    def get(self,_):return self.value
    def list(self,**_):return [self.value] if self.value else []
    def summary(self):return type("S",(),{})()
    def add_item(self,command_id,version,data,user):
        if self.reserved+data.base_units>24:raise ValueError("estoque disponível")
        self.reserved+=data.base_units; self.value.items.append(CommandItem(**data.model_dump(),item_id=f"i{len(self.value.items)+1}",user_id=user.id,username=user.username)); self.value.status=CommandStatus.SERVING; self.value.version+=1; return self.value
    def remove_item(self,command_id,version,item_id,user,reason):
        item=next(x for x in self.value.items if x.item_id==item_id); self.reserved-=item.base_units; self.value.items.remove(item); self.value.version+=1; return self.value
    def request_close(self,*_):self.value.status=CommandStatus.AWAITING_PAYMENT; self.value.version+=1; return self.value
    def reopen(self,*_):self.value.status=CommandStatus.SERVING; self.value.version+=1; return self.value
    def cancel(self,command_id,version,user,reason):self.reserved=0; self.value.status=CommandStatus.CANCELLED; self.value.version+=1; return self.value
    def finalize(self,command_id,version,sale):self.reserved=0; self.value.status=CommandStatus.FINALIZED; self.value.sale_id=sale.id; self.value.version+=1; return self.value
class Sales:
    def __init__(self):self.data=None
    def finalize(self,session,data):self.data=data; return type("Sale",(),{"id":"v1","payments":data.payments})()

def item(package=PackageType.UNIT,quantity=1):return CommandItemInput(product_id="p1",code="P1",product_name="Cerveja",package_type=package,quantity=quantity,units_per_pack=12,price=Decimal("5"))
def service_and_session(*permissions):
    repo=Repo(); return CommandService(repo,Audit()),repo,actor(*permissions)
def test_open_without_customer_requires_identification():
    with pytest.raises(ValueError,match="identificação"):CommandOpenInput(identification="")
def test_open_with_and_without_customer():
    service,repo,session=service_and_session(Permission.TABS_OPEN)
    assert service.open(session,CommandOpenInput(identification="Mesa 1")).number=="CMD-000001"
    assert service.open(session,CommandOpenInput(customer_id="x",customer_name="João")).customer_id=="x"
def test_unit_and_pack_conversion_and_reservation():
    service,repo,session=service_and_session(Permission.TABS_OPEN,Permission.TABS_ADD_ITEM); command=service.open(session,CommandOpenInput(identification="Mesa")); command=service.add_item(session,command.id,command.version,item()); command=service.add_item(session,command.id,command.version,item(PackageType.PACK,1)); assert repo.reserved==13; assert command.items[-1].base_units==12
def test_insufficient_available_stock():
    service,repo,session=service_and_session(Permission.TABS_OPEN,Permission.TABS_ADD_ITEM); command=service.open(session,CommandOpenInput(identification="Mesa"))
    with pytest.raises(ValueError,match="estoque"):service.add_item(session,command.id,command.version,item(PackageType.PACK,3))
def test_remove_releases_reservation_and_requires_reason():
    service,repo,session=service_and_session(Permission.TABS_OPEN,Permission.TABS_ADD_ITEM,Permission.TABS_REMOVE_ITEM); command=service.open(session,CommandOpenInput(identification="Mesa")); command=service.add_item(session,command.id,command.version,item(PackageType.PACK,1))
    with pytest.raises(ValueError,match="motivo"):service.remove_item(session,command.id,command.version,command.items[0].item_id,"")
    service.remove_item(session,command.id,command.version,command.items[0].item_id,"Erro"); assert repo.reserved==0
def test_cancel_releases_all_reservations():
    service,repo,session=service_and_session(Permission.TABS_OPEN,Permission.TABS_ADD_ITEM,Permission.TABS_CANCEL); command=service.open(session,CommandOpenInput(identification="Mesa")); command=service.add_item(session,command.id,command.version,item(PackageType.PACK,2)); service.cancel(session,command.id,command.version,"Cliente desistiu"); assert repo.reserved==0; assert repo.value.status==CommandStatus.CANCELLED
def test_permission_control():
    service,repo,session=service_and_session()
    with pytest.raises(PermissionError):service.open(session,CommandOpenInput(identification="Mesa"))
def test_mixed_payment_finalizes_one_sale_and_releases_reservation():
    repo=Repo(); sales=Sales(); service=CommandService(repo,Audit(),sales); session=actor(Permission.TABS_OPEN,Permission.TABS_ADD_ITEM,Permission.TABS_REQUEST_CLOSE,Permission.TABS_FINALIZE,Permission.TABS_VIEW); command=service.open(session,CommandOpenInput(identification="Mesa")); command=service.add_item(session,command.id,command.version,item()); command=service.request_close(session,command.id,command.version); result=service.finalize(session,command.id,command.version,[SalePayment(method=PaymentMethod.PIX,amount=Decimal("2")),SalePayment(method=PaymentMethod.CASH,amount=Decimal("3"))]); assert result.sale_id=="v1"; assert repo.reserved==0; assert sales.data.command_id==command.id
def test_fiado_requires_registered_customer():
    repo=Repo(); service=CommandService(repo,Audit(),Sales()); session=actor(Permission.TABS_OPEN,Permission.TABS_ADD_ITEM,Permission.TABS_REQUEST_CLOSE,Permission.TABS_FINALIZE,Permission.TABS_VIEW); command=service.open(session,CommandOpenInput(identification="Mesa")); command=service.add_item(session,command.id,command.version,item()); command=service.request_close(session,command.id,command.version)
    with pytest.raises(ValueError,match="vincule"):service.finalize(session,command.id,command.version,[SalePayment(method=PaymentMethod.STORE_CREDIT,amount=Decimal("5"))])
def test_pdf_conference(tmp_path:Path):
    service,repo,session=service_and_session(Permission.TABS_OPEN,Permission.TABS_ADD_ITEM,Permission.TABS_VIEW,Permission.TABS_PRINT); command=service.open(session,CommandOpenInput(identification="Mesa")); command=service.add_item(session,command.id,command.version,item()); path=tmp_path/"comanda.pdf"; service.export_pdf(session,command.id,path); assert path.read_bytes().startswith(b"%PDF"); assert path.stat().st_size>1000
