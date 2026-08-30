"""Testes do serviço e utilitários do dashboard."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from models.auth import AuthenticatedSession, Permission, ProfileCode, User
from models.dashboard import DashboardData, DashboardFilter
from services.dashboard import DashboardService
from services.rbac import AuthorizationError
from views.dashboard_view import DashboardView, brl


class FakeDashboardRepository:
    def __init__(self) -> None:
        self.calls = 0

    def load(self, filters: DashboardFilter) -> DashboardData:
        self.calls += 1
        return DashboardData(revenue_today=Decimal("1234.50"), sales_count=4)


def session_with(*permissions: Permission) -> AuthenticatedSession:
    user = User(username="teste", email="teste@example.com", full_name="Usuário Teste", profile_code=ProfileCode.MANAGER)
    return AuthenticatedSession(session_id="s1", user=user, permissions=set(permissions))


def filters() -> DashboardFilter:
    start = datetime.now(timezone.utc) - timedelta(days=7)
    return DashboardFilter(start_date=start, end_date=start + timedelta(days=8))


def test_dashboard_requires_permission() -> None:
    repository = FakeDashboardRepository()
    with pytest.raises(AuthorizationError):
        DashboardService(repository).load(session_with(), filters())
    assert repository.calls == 0


def test_dashboard_returns_repository_data() -> None:
    repository = FakeDashboardRepository()
    data = DashboardService(repository).load(session_with(Permission.DASHBOARD_VIEW), filters())
    assert data.sales_count == 4
    assert repository.calls == 1


def test_brl_format() -> None:
    assert brl(Decimal("1234.5")) == "R$ 1.234,50"

def test_visible_financial_cards_are_monetary() -> None:
    fields = {field: monetary for field, _, monetary in DashboardView.CARD_FIELDS}
    assert fields["revenue_today"] is True
    assert fields["current_cash"] is True
    assert fields["sales_month"] is True
    assert "average_ticket" not in fields
