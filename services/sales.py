"""Finalização transacional compensável de vendas do PDV."""
from decimal import Decimal
from models.auth import AuthenticatedSession, Permission
from models.sale import Sale, SaleInput
from models.stock import StockMovementRequest, StockMovementType
from repositories.auth import AuditRepository
from repositories.sales import SaleRepository
from services.rbac import require_permission
from services.stock import StockService
from services.cash import CashService
from services.credit import CreditService
from models.credit import CreditSaleAuthorization
from models.sale import PaymentMethod

class SaleService:
    def __init__(self, sales: SaleRepository, stock: StockService, audit: AuditRepository, cash: CashService | None = None, credit:CreditService|None=None): self.sales=sales; self.stock=stock; self.audit=audit; self.cash=cash; self.credit=credit
    def finalize(self, session: AuthenticatedSession, data: SaleInput) -> Sale:
        require_permission(session,Permission.POS_ACCESS)
        discount_limit=(data.subtotal*Decimal("0.10")).quantize(Decimal("0.01"))
        if data.total_discount>discount_limit and Permission.DISCOUNT_APPROVE not in session.permissions:raise PermissionError("Desconto acima de 10% exige autorização de gerente ou administrador.")
        if self.cash: self.cash.require_sale_allowed(session)
        credit_amount=sum((payment.amount for payment in data.payments if payment.method==PaymentMethod.STORE_CREDIT),Decimal("0"))
        sale=self.sales.create_pending(data,session.user); applied=[]; credit_prepared=False
        try:
            if credit_amount:
                if not self.credit:raise ValueError("Módulo de fiado indisponível.")
                self.credit.prepare_sale(session,sale,credit_amount,CreditSaleAuthorization(due_date=data.credit_due_date,allow_overdue=data.credit_allow_overdue,allow_over_limit=data.credit_allow_over_limit,justification=data.credit_justification)); credit_prepared=True
            for item in sale.items:
                request=StockMovementRequest(product_id=item.product_id,product_name=item.product_name,movement_type=StockMovementType.SALE_EXIT,package_type=item.package_type,informed_quantity=item.quantity,units_per_pack=item.units_per_pack,reason=f"Venda {sale.number}",related_document=sale.number)
                self.stock.sale_move(session,request); applied.append(item)
            sale=self.sales.complete(sale.id or "")
            if self.cash:self.cash.record_sale(session,sale)
            self.audit.record(user=session.user,action="venda_concluida",module="pdv",affected_id=sale.id,details={"numero":sale.number,"total":str(sale.total),"troco":str(sale.change)}); return sale
        except Exception:
            for item in reversed(applied):
                try: self.stock.sale_move(session,StockMovementRequest(product_id=item.product_id,product_name=item.product_name,movement_type=StockMovementType.RETURN_ENTRY,package_type=item.package_type,informed_quantity=item.quantity,units_per_pack=item.units_per_pack,reason=f"Compensação da venda {sale.number}",related_document=sale.number))
                except Exception: pass
            if credit_prepared:
                try:self.credit.rollback_sale(sale,credit_amount)
                except Exception:pass
            self.sales.fail(sale.id or ""); raise
