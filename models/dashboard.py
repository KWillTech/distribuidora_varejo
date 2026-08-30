"""Modelos de consulta e resposta do dashboard."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator


def start_of_today_utc() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


class DashboardFilter(BaseModel):
    start_date: datetime = Field(default_factory=lambda: start_of_today_utc() - timedelta(days=29))
    end_date: datetime = Field(default_factory=lambda: start_of_today_utc() + timedelta(days=1))
    user_id: str | None = None
    product_id: str | None = None
    category_id: str | None = None
    payment_method: str | None = None
    package_type: str | None = None

    @model_validator(mode="after")
    def validate_period(self) -> "DashboardFilter":
        if self.end_date <= self.start_date:
            raise ValueError("A data final deve ser posterior à data inicial.")
        return self


class ChartPoint(BaseModel):
    label: str
    value: Decimal = Decimal("0")


class DashboardData(BaseModel):
    sales_today: int = 0
    revenue_today: Decimal = Decimal("0")
    sales_month: Decimal = Decimal("0")
    average_ticket: Decimal = Decimal("0")
    sales_count: int = 0
    pending_orders: int = 0
    pending_deliveries: int = 0
    current_cash: Decimal = Decimal("0")
    cash_sales: Decimal = Decimal("0")
    pix_sales: Decimal = Decimal("0")
    debit_sales: Decimal = Decimal("0")
    credit_sales: Decimal = Decimal("0")
    expenses: Decimal = Decimal("0")
    estimated_profit: Decimal = Decimal("0")
    low_stock_products: int = 0
    expiring_products: int = 0
    credit_total:Decimal=Decimal("0"); credit_overdue:Decimal=Decimal("0"); credit_received_today:Decimal=Decimal("0"); credit_received_month:Decimal=Decimal("0"); credit_delinquent_customers:int=0; credit_near_limit_customers:int=0
    command_open:int=0; command_open_value:Decimal=Decimal("0"); command_awaiting:int=0; command_finalized_today:int=0; command_oldest_minutes:int=0
    sales_by_day: list[ChartPoint] = Field(default_factory=list)
    sales_by_month: list[ChartPoint] = Field(default_factory=list)
    sales_by_category: list[ChartPoint] = Field(default_factory=list)
    top_products: list[ChartPoint] = Field(default_factory=list)
    payment_methods: list[ChartPoint] = Field(default_factory=list)
    package_sales: list[ChartPoint] = Field(default_factory=list)
    revenue_series: list[ChartPoint] = Field(default_factory=list)
    cost_series: list[ChartPoint] = Field(default_factory=list)
    profit_series: list[ChartPoint] = Field(default_factory=list)
