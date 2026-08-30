"""Casos de uso e autorização do controle de comandas."""
from decimal import Decimal
from models.auth import Permission
from models.command import CommandItemInput,CommandOpenInput
from models.sale import PaymentMethod,SaleInput,SaleItem
from services.rbac import require_permission
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle
class CommandService:
    def __init__(self,repository,audit,sales=None):self.repository=repository; self.audit=audit; self.sales=sales
    def open(self,session,data:CommandOpenInput):
        require_permission(session,Permission.TABS_OPEN); command=self.repository.open(data,session.user); self._audit(session,"comanda_aberta",command,details={"cliente_id":data.customer_id,"tipo":data.service_type.value}); return command
    def list(self,session,**filters):require_permission(session,Permission.TABS_VIEW); return self.repository.list(**filters)
    def get(self,session,command_id):
        require_permission(session,Permission.TABS_VIEW); command=self.repository.get(command_id)
        if not command:raise ValueError("Comanda não encontrada.")
        return command
    def summary(self,session):require_permission(session,Permission.TABS_VIEW); return self.repository.summary()
    def add_item(self,session,command_id,version,data:CommandItemInput):
        require_permission(session,Permission.TABS_ADD_ITEM); result=self.repository.add_item(command_id,version,data,session.user); self._audit(session,"comanda_item_adicionado",result,details={"produto":data.product_name,"quantidade":data.quantity,"unidades":data.base_units,"tipo":data.package_type.value}); return result
    def remove_item(self,session,command_id,version,item_id,reason):
        require_permission(session,Permission.TABS_REMOVE_ITEM)
        if not reason.strip():raise ValueError("Informe o motivo da remoção.")
        result=self.repository.remove_item(command_id,version,item_id,session.user,reason); self._audit(session,"comanda_item_removido",result,reason); return result
    def request_close(self,session,command_id,version):
        require_permission(session,Permission.TABS_REQUEST_CLOSE); result=self.repository.request_close(command_id,version); self._audit(session,"comanda_fechamento_solicitado",result); return result
    def reopen(self,session,command_id,version,reason):
        require_permission(session,Permission.TABS_EDIT_ITEM)
        if not reason.strip():raise ValueError("Informe o motivo para reabrir.")
        result=self.repository.reopen(command_id,version); self._audit(session,"comanda_reaberta",result,reason); return result
    def finalize(self,session,command_id,version,payments,credit_due_date=None,credit_allow_overdue=False,credit_allow_over_limit=False,justification=None):
        require_permission(session,Permission.TABS_FINALIZE)
        if not self.sales:raise RuntimeError("Serviço de vendas indisponível.")
        command=self.get(session,command_id)
        if command.version!=version or command.status.value!="aguardando_pagamento":raise ValueError("Solicite o fechamento e atualize a comanda antes de finalizar.")
        if command.sale_id:return command
        if any(p.method==PaymentMethod.STORE_CREDIT for p in payments) and not command.customer_id:raise ValueError("Para utilizar fiado, vincule esta comanda a um cliente cadastrado.")
        items=[SaleItem(product_id=i.product_id,product_name=i.product_name,package_type=i.package_type,quantity=i.quantity,units_per_pack=i.units_per_pack,unit_price=i.price,discount=i.discount) for i in command.items]
        data=SaleInput(command_id=command.id,customer_id=command.customer_id,customer_name=command.customer_name or command.identification,items=items,total_discount=command.discount,surcharge=command.surcharge,delivery_fee=command.delivery_fee,notes=f"Comanda {command.number}",payments=payments,credit_due_date=credit_due_date,credit_allow_overdue=credit_allow_overdue,credit_allow_over_limit=credit_allow_over_limit,credit_justification=justification)
        sale=self.sales.finalize(session,data)
        try:result=self.repository.finalize(command_id,version,sale)
        except Exception:
            self.audit.record(user=session.user,action="comanda_finalizacao_pendente",module="comandas",affected_id=command_id,details={"venda_id":sale.id}); raise
        self._audit(session,"comanda_finalizada",result,details={"venda_id":sale.id,"total":str(result.total)}); return result
    def cancel(self,session,command_id,version,reason):
        require_permission(session,Permission.TABS_CANCEL)
        if not reason.strip():raise ValueError("Informe o motivo do cancelamento.")
        result=self.repository.cancel(command_id,version,session.user,reason); self._audit(session,"comanda_cancelada",result,reason); return result
    def merge(self,session,source,target,source_version,target_version,reason):
        require_permission(session,Permission.TABS_MERGE)
        if not reason.strip():raise ValueError("Informe o motivo da união.")
        result=self.repository.transfer_all(source,target,source_version,target_version,session.user,reason); self._audit(session,"comandas_unidas",result,reason,{"origem":source,"destino":target}); return result
    def export_pdf(self,session,command_id,path):
        money=lambda value:f"R$ {value:,.2f}".replace(",","X").replace(".",",").replace("X","."); require_permission(session,Permission.TABS_PRINT); command=self.get(session,command_id); styles=getSampleStyleSheet(); story=[Paragraph("Adega do Bruninho",styles["Title"]),Paragraph(f"Conferência da comanda {command.number}",styles["Heading2"]),Paragraph(f"Cliente/identificação: {command.identification}<br/>Abertura: {command.opened_at:%d/%m/%Y %H:%M}<br/>Atendimento: {command.service_type.value.title()}<br/>Status: {command.status.value.replace('_',' ').title()}",styles["BodyText"]),Spacer(1,12)]; rows=[["Produto","Tipo","Qtd.","Unidades","Preço","Desconto","Subtotal"]]+[[i.product_name,i.package_type.value.title(),str(i.quantity),str(i.base_units),money(i.price),money(i.discount),money(i.subtotal)] for i in command.items]; table=Table(rows,repeatRows=1,colWidths=[180,60,40,50,65,65,70]); table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#171717")),("TEXTCOLOR",(0,0),(-1,0),colors.HexColor("#FFB000")),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("GRID",(0,0),(-1,-1),.35,colors.grey),("FONTSIZE",(0,0),(-1,-1),8),("VALIGN",(0,0),(-1,-1),"TOP")])) ; story.extend([table,Spacer(1,12),Paragraph(f"Subtotal: {money(command.subtotal)}<br/>Desconto: {money(command.discount)}<br/>Taxa de entrega: {money(command.delivery_fee)}<br/><b>Total: {money(command.total)}</b>",styles["BodyText"])]); 
        if command.payments:story.extend([Spacer(1,8),Paragraph("Pagamentos: "+"; ".join(f"{p['forma'].replace('_',' ').title()}: {money(p['valor'])}" for p in command.payments),styles["BodyText"])])
        doc=SimpleDocTemplate(str(path),pagesize=A4,rightMargin=28,leftMargin=28,topMargin=28,bottomMargin=28); doc.build(story); self._audit(session,"comanda_impressa",command,details={"arquivo":str(path),"reimpressao":command.status.value=="finalizada"}); return path
    def _audit(self,session,action,command,reason=None,details=None):self.audit.record(user=session.user,action=action,module="comandas",affected_id=command.id,reason=reason,details={"comanda":command.number,"perfil":session.user.profile_code.value,**(details or {})})
