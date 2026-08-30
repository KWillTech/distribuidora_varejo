from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Lock

import pytest

from models.auth import AuthenticatedSession, Permission, ProfileCode, User
from models.credit import CreditProfile, CreditSaleAuthorization
from models.sale import PaymentMethod, SaleInput, SaleItem, SalePayment
from services.credit import CreditService


def session(*permissions):
    user = User(id="u1", username="gerente", email="g@example.com", full_name="Gerente", profile_code=ProfileCode.MANAGER)
    return AuthenticatedSession(session_id="s1", user=user, permissions=set(permissions))


class Audit:
    def __init__(self): self.rows=[]
    def record(self, **kwargs): self.rows.append(kwargs)


class AtomicRepository:
    def __init__(self, *, enabled=True, status="liberado", overdue=False, limit=Decimal("100"), debt=Decimal("0")):
        self.customer={"_id":"c1","ativo":True,"fiado_habilitado":enabled,"fiado_status":status,"fiado_permitir_vencido":False,"fiado_limite_credito":limit,"fiado_saldo_devedor":debt}
        self.overdue=overdue; self.lock=Lock(); self.accounts=[]
    def customer_document(self, _): return self.customer
    def has_overdue(self, _): return self.overdue
    def reserve_credit(self, _, amount, allow=False):
        with self.lock:
            previous=self.customer["fiado_saldo_devedor"]
            limit=self.customer["fiado_limite_credito"]
            if not allow and previous+amount>limit: raise ValueError("limite de crédito insuficiente")
            self.customer["fiado_saldo_devedor"]=previous+amount
            return previous,limit,max(Decimal("0"),previous+amount-limit)
    def release_credit(self, _, amount):
        with self.lock:self.customer["fiado_saldo_devedor"]-=amount
    def create_account(self, sale, amount, due_date, user, authorization):
        account=type("Account",(),{"id":f"a{len(self.accounts)+1}"})(); self.accounts.append((sale,amount,due_date)); return account
    def rollback_sale(self,*_): pass


def sale():
    return type("Sale",(),{"id":"v1","number":"V-1","customer_id":"c1","customer_name":"Cliente","created_at":None,"notes":None})()


def authorization(**kwargs):
    return CreditSaleAuthorization(due_date=date(2026,9,10), **kwargs)


def test_available_limit_never_negative():
    profile=CreditProfile(enabled=True,credit_limit=Decimal("50"),debt_balance=Decimal("70"))
    assert profile.available_limit==Decimal("0")


def test_mixed_payment_creates_only_fiado_portion():
    item=SaleItem(product_id="p1",product_name="Cerveja",package_type="unidade",quantity=1,units=1,unit_price=Decimal("150"),unit_cost=Decimal("80"),subtotal=Decimal("150"))
    value=SaleInput(customer_id="c1",customer_name="Cliente",credit_due_date=date(2026,9,10),items=[item],payments=[SalePayment(method=PaymentMethod.PIX,amount=Decimal("50")),SalePayment(method=PaymentMethod.STORE_CREDIT,amount=Decimal("100"))])
    assert sum(p.amount for p in value.payments if p.method==PaymentMethod.STORE_CREDIT)==Decimal("100")


@pytest.mark.parametrize("repository,message",[
    (AtomicRepository(enabled=False),"não possui fiado habilitado"),
    (AtomicRepository(status="bloqueado_manual"),"bloqueado"),
    (AtomicRepository(overdue=True),"contas vencidas"),
])
def test_credit_sale_rejections(repository,message):
    service=CreditService(repository,Audit())
    with pytest.raises(ValueError,match=message):service.prepare_sale(session(Permission.CREDIT_SALE),sale(),Decimal("10"),authorization())


def test_sale_inside_limit_and_above_limit():
    repository=AtomicRepository(limit=Decimal("100")); service=CreditService(repository,Audit()); actor=session(Permission.CREDIT_SALE)
    service.prepare_sale(actor,sale(),Decimal("80"),authorization())
    assert repository.customer["fiado_saldo_devedor"]==Decimal("80")
    with pytest.raises(ValueError,match="limite"):service.prepare_sale(actor,sale(),Decimal("30"),authorization())


def test_atomic_limit_allows_only_one_concurrent_sale():
    repository=AtomicRepository(limit=Decimal("100")); service=CreditService(repository,Audit()); actor=session(Permission.CREDIT_SALE)
    def run():
        try: service.prepare_sale(actor,sale(),Decimal("60"),authorization()); return True
        except ValueError: return False
    with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(lambda _:run(),range(2)))
    assert sorted(results)==[False,True]
    assert repository.customer["fiado_saldo_devedor"]==Decimal("60")


def test_overdue_release_requires_permission_and_justification():
    repository=AtomicRepository(overdue=True); service=CreditService(repository,Audit())
    with pytest.raises(ValueError,match="justificativa"):service.prepare_sale(session(Permission.CREDIT_SALE,Permission.CREDIT_RELEASE_OVERDUE),sale(),Decimal("10"),authorization(allow_overdue=True))
    service.prepare_sale(session(Permission.CREDIT_SALE,Permission.CREDIT_RELEASE_OVERDUE),sale(),Decimal("10"),authorization(allow_overdue=True,justification="Autorizado após análise"))

