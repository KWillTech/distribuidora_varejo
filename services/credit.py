"""Casos de uso autorizados do controle de fiado."""
from decimal import Decimal
from bson.decimal128 import Decimal128
from models.auth import Permission,ProfileCode
from models.credit import CreditAdjustmentInput,CreditMovementType,CreditPaymentInput,CreditSaleAuthorization,RenegotiationInput
from services.rbac import require_permission
class CreditService:
    def __init__(self,repository,audit,cash=None):self.repository=repository; self.audit=audit; self.cash=cash
    def customer_status(self,session,customer_id):require_permission(session,Permission.CREDIT_VIEW); return self.repository.customer_document(customer_id),self.repository.list_accounts(customer_id),self.repository.has_overdue(customer_id)
    def prepare_sale(self,session,sale,amount,authorization:CreditSaleAuthorization):
        require_permission(session,Permission.CREDIT_SALE); customer=self.repository.customer_document(sale.customer_id or "")
        if not customer or not customer.get("ativo",True):raise ValueError("Cliente inexistente ou inativo.")
        if not customer.get("fiado_habilitado",False):raise ValueError("Cliente não possui fiado habilitado.")
        if customer.get("fiado_status") in ("bloqueado_manual","inativo"):raise ValueError("Cliente bloqueado para novas compras.")
        overdue=self.repository.has_overdue(sale.customer_id)
        if overdue and not customer.get("fiado_permitir_vencido",False):
            if not authorization.allow_overdue or Permission.CREDIT_RELEASE_OVERDUE not in session.permissions:raise ValueError("Cliente possui contas vencidas. É necessária autorização do gerente.")
            if not (authorization.justification or "").strip():raise ValueError("Informe a justificativa para liberar cliente inadimplente.")
        if authorization.allow_over_limit and Permission.CREDIT_EXCEED_LIMIT not in session.permissions:raise PermissionError("É necessária autorização para ultrapassar o limite.")
        previous,limit,excess=self.repository.reserve_credit(sale.customer_id,amount,authorization.allow_over_limit)
        try:account=self.repository.create_account(sale,amount,authorization.due_date,session.user,authorization)
        except Exception:self.repository.release_credit(sale.customer_id,amount); raise
        self.audit.record(user=session.user,action="venda_fiada_registrada",module="fiado",affected_id=account.id,reason=authorization.justification,details={"cliente_id":sale.customer_id,"venda":sale.number,"valor":str(amount),"saldo_anterior":str(previous),"saldo_novo":str(previous+amount),"limite":str(limit),"excesso":str(excess),"vencimento":str(authorization.due_date)}); return account
    def rollback_sale(self,sale,amount):self.repository.rollback_sale(sale.id or "",sale.customer_id or "",amount)
    def list_accounts(self,session,customer_id=None,status=None):require_permission(session,Permission.CREDIT_VIEW); return self.repository.list_accounts(customer_id,status)
    def movements(self,session,customer_id):require_permission(session,Permission.CREDIT_VIEW); return self.repository.movements_for_customer(customer_id)
    def payments(self,session,customer_id=None):require_permission(session,Permission.CREDIT_VIEW); return self.repository.payments_list(customer_id)
    def summary(self,session):require_permission(session,Permission.CREDIT_VIEW); return self.repository.summary()
    def receive(self,session,customer_id,data:CreditPaymentInput):
        require_permission(session,Permission.CREDIT_RECEIVE); cash_id=None
        if self.cash:
            if session.user.profile_code==ProfileCode.FINANCE and data.notes:cash=None
            else:cash=self.cash.require_open(session); cash_id=cash.id
        payment_id,applied=self.repository.receive(customer_id,data.amount,data.payment_method,session.user,cash_id,data.account_ids,data.notes)
        if self.cash and cash_id:self.cash.record_credit_receipt(session,data.amount,data.payment_method,payment_id)
        self.audit.record(user=session.user,action="pagamento_fiado_recebido",module="fiado",affected_id=payment_id,details={"cliente_id":customer_id,"valor":str(data.amount),"contas":[str(d["_id"]) for d,_ in applied],"caixa_id":cash_id}); return payment_id
    def configure_customer(self,session,customer_id,enabled,limit,due_day,due_days,allow_overdue,notes):
        customer=self.repository.customer_document(customer_id)
        if not customer:raise ValueError("Cliente não encontrado.")
        current_enabled=bool(customer.get("fiado_habilitado",False)); current_limit=customer.get("fiado_limite_credito")
        current_limit=current_limit.to_decimal() if isinstance(current_limit,Decimal128) else Decimal(str(current_limit or 0))
        if enabled!=current_enabled:require_permission(session,Permission.CREDIT_ENABLE)
        if limit!=current_limit:require_permission(session,Permission.CREDIT_LIMIT)
        if limit<0:raise ValueError("Limite inválido.")
        result=self.repository.customers.update_one({"_id":customer["_id"]},{"$set":{"fiado_habilitado":enabled,"fiado_limite_credito":Decimal128(limit),"fiado_dia_vencimento":due_day,"fiado_dias_vencimento":due_days,"fiado_permitir_vencido":allow_overdue,"fiado_observacoes":notes,"fiado_status":"liberado" if enabled else "inativo"}})
        self.audit.record(user=session.user,action="fiado_cliente_configurado",module="fiado",affected_id=customer_id,details={"habilitado_anterior":current_enabled,"habilitado_novo":enabled,"limite_anterior":str(current_limit),"limite_novo":str(limit)}); return result.modified_count==1
    def block_customer(self,session,customer_id,blocked,reason):
        require_permission(session,Permission.CREDIT_BLOCK if blocked else Permission.CREDIT_UNBLOCK)
        if not reason.strip():raise ValueError("Informe o motivo.")
        from models.auth import utc_now
        self.repository.customers.update_one({"_id":self.repository.customer_document(customer_id)["_id"]},{"$set":{"fiado_status":"bloqueado_manual" if blocked else "liberado","fiado_motivo_bloqueio":reason,"fiado_bloqueado_em":utc_now() if blocked else None,"fiado_bloqueado_por":session.user.username}}); self.audit.record(user=session.user,action="fiado_bloqueado" if blocked else "fiado_desbloqueado",module="fiado",affected_id=customer_id,reason=reason)
    def adjust(self,session,account_id,kind,data:CreditAdjustmentInput):
        permission=Permission.CREDIT_DISCOUNT if kind==CreditMovementType.DISCOUNT else Permission.CREDIT_INTEREST; require_permission(session,permission); account=self.repository.adjust(account_id,kind,data.amount,session.user,data.reason); self.audit.record(user=session.user,action=kind.value,module="fiado",affected_id=account.id,reason=data.reason,details={"valor":str(data.amount),"saldo":str(account.open_balance)}); return account
    def reverse_payment(self,session,payment_id,reason):
        require_permission(session,Permission.CREDIT_REVERSE_PAYMENT)
        if not reason.strip():raise ValueError("Informe o motivo do estorno.")
        total,payment=self.repository.reverse_payment(payment_id,session.user,reason)
        if self.cash and payment.get("caixa_id"):self.cash.reverse_credit_receipt(session,total,payment_id,reason)
        self.audit.record(user=session.user,action="pagamento_fiado_estornado",module="fiado",affected_id=payment_id,reason=reason,details={"valor":str(total),"caixa_id":payment.get("caixa_id")}); return total
    def cancel_account(self,session,account_id,reason):
        require_permission(session,Permission.CREDIT_CANCEL)
        if not reason.strip():raise ValueError("Informe o motivo do cancelamento.")
        account=self.repository.cancel_account(account_id,session.user,reason); self.audit.record(user=session.user,action="conta_fiado_cancelada",module="fiado",affected_id=account.id,reason=reason,details={"saldo_cancelado":str(account.open_balance)}); return account
    def renegotiate(self,session,customer_id,data:RenegotiationInput):
        require_permission(session,Permission.CREDIT_RENEGOTIATE)
        if data.interest and Permission.CREDIT_INTEREST not in session.permissions:raise PermissionError("Sem permissão para aplicar juros.")
        if data.discount and Permission.CREDIT_DISCOUNT not in session.permissions:raise PermissionError("Sem permissão para aplicar desconto.")
        accounts=self.repository.renegotiate(customer_id,data.account_ids,data.new_due_date,data.installments,data.interest,data.discount,session.user,data.justification); self.audit.record(user=session.user,action="fiado_renegociado",module="fiado",affected_id=accounts[0].id,reason=data.justification,details={"parcelas":data.installments,"juros":str(data.interest),"desconto":str(data.discount)}); return accounts
