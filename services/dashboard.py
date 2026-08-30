"""Serviço autorizado do dashboard."""

from models.auth import AuthenticatedSession, Permission
from models.dashboard import DashboardData, DashboardFilter
from repositories.dashboard import DashboardRepository
from services.rbac import require_permission


class DashboardService:
    def __init__(self, repository: DashboardRepository) -> None:
        self._repository = repository

    def load(self, session: AuthenticatedSession, filters: DashboardFilter) -> DashboardData:
        require_permission(session, Permission.DASHBOARD_VIEW)
        return self._repository.load(filters)
