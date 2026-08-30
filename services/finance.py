"""Regras e autorização do financeiro."""
from models.auth import Permission
from models.finance import FinancialInput,FinancialKind,FinancialStatus,PaymentInput
from services.rbac import require_permission
class FinanceService:
    def __init__(self,repository,audit):self.repository=repository; self.audit=audit
    def list(self,session,kind=None,status=None):require_permission(session,Permission.FINANCE_VIEW); return self.repository.list(kind,status)
    def create(self,session,data:FinancialInput):
        require_permission(session,Permission.FINANCE_MANAGE)
        if data.kind not in (FinancialKind.EXPENSE,FinancialKind.REVENUE,FinancialKind.RECEIVABLE):raise ValueError("Contas de compras são geradas automaticamente.")
        entry=self.repository.create(data); self._audit(session,"lancamento_financeiro_criado",entry); return entry
    def pay(self,session,kind,entry_id,data:PaymentInput):
        require_permission(session,Permission.FINANCE_MANAGE); entry=self.repository.pay(kind,entry_id,data,session.user); self._audit(session,"pagamento_financeiro_registrado",entry); return entry
    def update_expense(self,session,entry_id,data:FinancialInput):
        require_permission(session,Permission.FINANCE_MANAGE)
        if data.kind!=FinancialKind.EXPENSE:raise ValueError("Somente despesas podem ser editadas por esta opção.")
        entry=self.repository.update_expense(entry_id,data); self._audit(session,"despesa_editada",entry); return entry
    def delete_expense(self,session,entry_id,reason):
        require_permission(session,Permission.FINANCE_MANAGE)
        if not reason.strip():raise ValueError("Informe o motivo da exclusão.")
        entry=self.repository.cancel_expense(entry_id,reason.strip()); self.audit.record(user=session.user,action="despesa_excluida",module="financeiro",affected_id=entry.id,reason=reason.strip(),details={"valor":str(entry.original_amount)}); return entry
    def delete_expenses(self,session,entries,reason):
        require_permission(session,Permission.FINANCE_MANAGE)
        if not reason.strip():raise ValueError("Informe o motivo da exclusão.")
        if not entries:raise ValueError("Selecione ao menos uma despesa.")
        invalid=[entry for entry in entries if entry.kind!=FinancialKind.EXPENSE or entry.status!=FinancialStatus.OPEN or entry.paid_amount!=0]
        if invalid:raise ValueError("A seleção contém itens que não são despesas abertas e sem pagamentos.")
        count=self.repository.cancel_expenses([entry.id for entry in entries],reason.strip())
        if count!=len(entries):raise ValueError(f"Foram excluídas {count} de {len(entries)} despesas. Atualize a lista e verifique os itens restantes.")
        self.audit.record(user=session.user,action="despesas_excluidas",module="financeiro",reason=reason.strip(),details={"quantidade":count,"ids":[entry.id for entry in entries]}); return count
    def summary(self,session):
        entries=self.list(session); result={"pagar":0,"receber":0,"despesas":0,"receitas":0}
        for e in entries:
            if e.status==FinancialStatus.CANCELLED:continue
            if e.kind==FinancialKind.PAYABLE:result["pagar"]+=e.balance
            elif e.kind==FinancialKind.RECEIVABLE:result["receber"]+=e.balance
            elif e.kind==FinancialKind.EXPENSE:result["despesas"]+=e.original_amount
            elif e.kind==FinancialKind.REVENUE:result["receitas"]+=e.original_amount
        return result
    def _audit(self,session,action,entry):self.audit.record(user=session.user,action=action,module="financeiro",affected_id=entry.id,details={"tipo":entry.kind.value,"valor":str(entry.original_amount),"saldo":str(entry.balance)})
