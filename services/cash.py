"""Regras autorizadas de operação do caixa."""
from decimal import Decimal
from models.auth import AuthenticatedSession,Permission
from models.cash import CashCloseInput,CashMovementInput,CashMovementType,CashRegister
from repositories.auth import AuditRepository
from repositories.cash import CashRepository
from services.rbac import require_permission
class CashService:
    WITHDRAWAL_LIMIT = Decimal("500.00")
    WITHDRAWAL_REQUIRED_MESSAGE = (
        "Sangria obrigatória: o caixa atingiu R$ 500,00. "
        "Realize uma sangria antes de fazer outra venda."
    )
    def __init__(self,repository:CashRepository,audit:AuditRepository): self.repository=repository; self.audit=audit
    def current(self,session): return self.repository.get_open(session.user.id or session.user.username)
    def require_open(self,session)->CashRegister:
        cash=self.current(session)
        if not cash: raise ValueError("Abra o caixa antes de realizar vendas.")
        return cash
    def withdrawal_required(self,session)->bool:
        cash=self.current(session)
        return bool(cash and cash.expected_amount >= self.WITHDRAWAL_LIMIT)
    def require_sale_allowed(self,session)->CashRegister:
        cash=self.require_open(session)
        if cash.expected_amount >= self.WITHDRAWAL_LIMIT:
            raise ValueError(self.WITHDRAWAL_REQUIRED_MESSAGE)
        return cash
    def open(self,session,amount:Decimal):
        require_permission(session,Permission.CASH_OPEN); cash=self.repository.open(session.user,amount); self.audit.record(user=session.user,action="caixa_aberto",module="caixa",affected_id=cash.id,details={"valor":str(amount)}); return cash
    def supply(self,session,amount,reason): require_permission(session,Permission.CASH_OPEN); return self._move(session,CashMovementType.SUPPLY,amount,reason)
    def withdraw(self,session,amount,reason): require_permission(session,Permission.CASH_WITHDRAW); return self._move(session,CashMovementType.WITHDRAWAL,amount,reason)
    def _move(self,session,kind,amount,reason):
        cash=self.require_open(session); result=self.repository.add_movement(cash.id or "",session.user,CashMovementInput(movement_type=kind,amount=amount,reason=reason)); self.audit.record(user=session.user,action=kind.value,module="caixa",affected_id=cash.id,reason=reason,details={"valor":str(amount)}); return result
    def record_sale(self,session,sale):
        cash=self.require_open(session)
        for payment in sale.payments:
            if payment.method.value!="fiado":self.repository.add_movement(cash.id or "",session.user,CashMovementInput(movement_type=CashMovementType.SALE,amount=payment.amount,payment_method=payment.method.value,reason=f"Venda {sale.number}",related_document=sale.number))
    def record_credit_receipt(self,session,amount,method,payment_id):
        cash=self.require_open(session); return self.repository.add_movement(cash.id or "",session.user,CashMovementInput(movement_type=CashMovementType.CREDIT_RECEIPT,amount=amount,payment_method=method,reason="Recebimento de fiado",related_document=payment_id))
    def reverse_credit_receipt(self,session,amount,payment_id,reason):
        cash=self.require_open(session); return self.repository.add_movement(cash.id or "",session.user,CashMovementInput(movement_type=CashMovementType.REVERSAL,amount=amount,reason=f"Estorno de fiado: {reason}",related_document=payment_id))
    def close(self,session,data:CashCloseInput):
        require_permission(session,Permission.CASH_CLOSE); cash=self.require_open(session); result=self.repository.close(cash.id or "",data); self.audit.record(user=session.user,action="caixa_fechado",module="caixa",affected_id=cash.id,details={"esperado":str(result.expected_amount),"contado":str(result.counted_amount),"diferenca":str(result.difference)}); return result
    def history(self,session): require_permission(session,Permission.CASH_OPEN); return self.repository.history()
