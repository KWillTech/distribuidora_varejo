"""Regras de pedidos e entregas."""
from models.auth import Permission
from models.order import OrderInput,OrderStatus
from services.rbac import require_permission

TRANSITIONS={OrderStatus.AWAITING_PAYMENT:{OrderStatus.PAID,OrderStatus.CANCELLED},OrderStatus.PAID:{OrderStatus.SEPARATING,OrderStatus.CANCELLED},OrderStatus.SEPARATING:{OrderStatus.READY_PICKUP,OrderStatus.READY_DELIVERY,OrderStatus.CANCELLED},OrderStatus.READY_DELIVERY:{OrderStatus.OUT_FOR_DELIVERY,OrderStatus.CANCELLED},OrderStatus.OUT_FOR_DELIVERY:{OrderStatus.DELIVERED,OrderStatus.NOT_DELIVERED},OrderStatus.NOT_DELIVERED:{OrderStatus.READY_DELIVERY,OrderStatus.CANCELLED},OrderStatus.READY_PICKUP:{OrderStatus.DELIVERED,OrderStatus.CANCELLED}}

class OrderService:
    def __init__(self,repository,audit):self.repository=repository; self.audit=audit
    def list(self,session):
        if Permission.DELIVERIES_MANAGE in session.permissions:return self.repository.list()
        if Permission.DELIVERIES_OWN in session.permissions:return self.repository.list(session.user.id or session.user.username)
        require_permission(session,Permission.ORDERS_CREATE); return self.repository.list(created_by=session.user.username)
    def create(self,session,data:OrderInput):
        if Permission.DELIVERIES_MANAGE not in session.permissions:require_permission(session,Permission.ORDERS_CREATE)
        order=self.repository.create(data,session.user); self._audit(session,"pedido_criado",order); return order
    def assign(self,session,order_id,person_id,name):
        require_permission(session,Permission.DELIVERIES_MANAGE)
        if not name.strip():raise ValueError("Informe o entregador.")
        order=self.repository.assign(order_id,person_id.strip() or name.strip(),name.strip()); self._audit(session,"entregador_atribuido",order); return order
    def update_status(self,session,order_id,status:OrderStatus):
        order=self.repository.get(order_id)
        if not order:raise ValueError("Pedido não encontrado.")
        if Permission.DELIVERIES_MANAGE not in session.permissions:
            require_permission(session,Permission.DELIVERIES_OWN)
            if order.delivery_person_id not in (session.user.id,session.user.username):raise PermissionError("Pedido atribuído a outro entregador.")
        if status not in TRANSITIONS.get(order.status,set()):raise ValueError("Alteração de status não permitida.")
        result=self.repository.update_status(order_id,status); self._audit(session,"status_entrega_alterado",result); return result
    def occurrence(self,session,order_id,text):
        if not text.strip():raise ValueError("Informe a ocorrência.")
        order=self.repository.get(order_id)
        if not order:raise ValueError("Pedido não encontrado.")
        if Permission.DELIVERIES_MANAGE not in session.permissions and order.delivery_person_id not in (session.user.id,session.user.username):raise PermissionError("Pedido atribuído a outro entregador.")
        result=self.repository.occurrence(order_id,text.strip()); self._audit(session,"ocorrencia_entrega",result); return result
    def _audit(self,session,action,order):self.audit.record(user=session.user,action=action,module="pedidos_entregas",affected_id=order.id,details={"numero":order.number,"status":order.status.value})
