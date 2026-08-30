"""Regras autorizadas de estoque, lotes, validade e inventário."""

from datetime import datetime, timedelta, timezone

from models.auth import AuthenticatedSession, Permission, ProfileCode
from models.stock import InventoryRequest, StockLot, StockMovement, StockMovementRequest, StockMovementType
from repositories.auth import AuditRepository
from repositories.stock import StockRepository
from services.rbac import require_permission


class StockService:
    def __init__(self, repository: StockRepository, audit: AuditRepository) -> None:
        self._repository = repository; self._audit = audit

    def move(self, session: AuthenticatedSession, request: StockMovementRequest, allow_negative: bool = False) -> StockMovement:
        require_permission(session, Permission.STOCK_ADJUST)
        if allow_negative and session.user.profile_code != ProfileCode.ADMIN:
            raise PermissionError("Somente administrador pode autorizar estoque negativo.")
        movement = self._repository.apply(request, session.user, allow_negative)
        self._audit.record(user=session.user, action="movimentacao_estoque", module="estoque", affected_id=request.product_id, reason=request.reason, details={"tipo": request.movement_type.value, "unidades": movement.converted_units, "saldo_anterior": movement.balance_before, "saldo_final": movement.balance_after})
        return movement

    def inventory(self, session: AuthenticatedSession, request: InventoryRequest) -> StockMovement:
        require_permission(session, Permission.STOCK_ADJUST); movement = self._repository.inventory(request, session.user)
        self._audit.record(user=session.user, action="inventario_realizado", module="estoque", affected_id=request.product_id, reason=request.reason, details={"saldo_anterior": movement.balance_before, "saldo_contado": movement.balance_after})
        return movement

    def sale_move(self, session: AuthenticatedSession, request: StockMovementRequest) -> StockMovement:
        """Movimenta somente saída/compensação originada pelo PDV."""
        require_permission(session, Permission.POS_ACCESS)
        if request.movement_type not in (StockMovementType.SALE_EXIT, StockMovementType.RETURN_ENTRY): raise ValueError("Movimentação inválida para o PDV.")
        movement = self._repository.apply(request, session.user, False)
        self._audit.record(user=session.user, action="movimentacao_estoque_venda", module="estoque", affected_id=request.product_id, reason=request.reason, details={"tipo": request.movement_type.value, "unidades": movement.converted_units, "saldo_anterior": movement.balance_before, "saldo_final": movement.balance_after})
        return movement

    def list_movements(self, session: AuthenticatedSession, **filters) -> tuple[list[StockMovement], int]:
        require_permission(session, Permission.STOCK_VIEW); return self._repository.list_movements(**filters)

    def list_lots(self, session: AuthenticatedSession, product_id: str | None = None) -> list[StockLot]:
        require_permission(session, Permission.STOCK_VIEW); return self._repository.list_lots(product_id=product_id)

    def expiring_lots(self, session: AuthenticatedSession, days: int = 30) -> list[StockLot]:
        require_permission(session, Permission.STOCK_VIEW)
        if days < 0 or days > 3650: raise ValueError("Período de validade inválido.")
        limit = datetime.now(timezone.utc) + timedelta(days=days)
        return self._repository.list_lots(expiring_until=limit)
