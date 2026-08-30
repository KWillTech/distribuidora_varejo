"""Consultas agregadas do dashboard no MongoDB."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from pymongo.database import Database
from bson.decimal128 import Decimal128

from models.dashboard import ChartPoint, DashboardData, DashboardFilter


def _decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    return value.to_decimal() if isinstance(value, Decimal128) else Decimal(str(value))


class DashboardRepository:
    """Executa somente consultas; regras de autorização ficam no serviço."""

    def __init__(self, database: Database) -> None:
        self._sales = database["vendas"]
        self._orders = database["pedidos"]
        self._deliveries = database["entregas"]
        self._cash = database["caixas"]
        self._expenses = database["despesas"]
        self._products = database["produtos"]
        self._receivables=database["contas_receber"]; self._credit_payments=database["pagamentos_fiado"]; self._customers=database["clientes"]
        self._commands=database["comandas"]

    @staticmethod
    def _match(filters: DashboardFilter) -> dict[str, Any]:
        match: dict[str, Any] = {
            "data_hora": {"$gte": filters.start_date, "$lt": filters.end_date},
            "status": {"$in": ["concluida", "finalizada", "paga"]},
        }
        if filters.user_id:
            match["usuario_id"] = filters.user_id
        if filters.product_id:
            match["itens.produto_id"] = filters.product_id
        if filters.category_id:
            match["itens.categoria_id"] = filters.category_id
        if filters.payment_method:
            match["pagamentos.forma"] = filters.payment_method
        if filters.package_type:
            match["itens.tipo_embalagem"] = filters.package_type
        return match

    def load(self, filters: DashboardFilter) -> DashboardData:
        match = self._match(filters)
        summary = list(self._sales.aggregate([
            {"$match": match},
            {"$group": {"_id": None, "total": {"$sum": "$total"}, "cost": {"$sum": "$custo_total"}, "count": {"$sum": 1}}},
        ]))
        values = summary[0] if summary else {}
        total = _decimal(values.get("total"))
        count = int(values.get("count", 0))
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        month = today.replace(day=1)
        today_values = self._sum_sales(today, today + timedelta(days=1))
        month_values = self._sum_sales(month, today + timedelta(days=1))
        payments = self._group_payments(match)
        expenses = self._sum_collection(self._expenses, "valor", filters.start_date, filters.end_date)
        open_cash = self._cash.find_one({"status": "aberto"}, sort=[("aberto_em", -1)]) or {}
        zero = Decimal128(Decimal("0"))
        credit_open = list(self._receivables.aggregate([{"$match": {"origem": "fiado", "status": {"$nin": ["pago", "cancelado", "renegociado"]}}}, {"$group": {"_id": None, "total": {"$sum": "$saldo_aberto"}}}]))
        credit_overdue = list(self._receivables.aggregate([{"$match": {"origem": "fiado", "saldo_aberto": {"$gt": zero}, "vencimento": {"$lt": today}, "status": {"$nin": ["pago", "cancelado", "renegociado"]}}}, {"$group": {"_id": None, "total": {"$sum": "$saldo_aberto"}, "customers": {"$addToSet": "$cliente_id"}}}]))
        credit_today = self._sum_credit_payments(today, today + timedelta(days=1))
        credit_month = self._sum_credit_payments(month, today + timedelta(days=1))
        active_commands=list(self._commands.find({"status":{"$in":["aberta","em_atendimento","aguardando_pagamento"]}},{"status":1,"total":1,"data_abertura":1})); oldest=min((x.get("data_abertura") for x in active_commands if x.get("data_abertura")),default=None)
        return DashboardData(
            sales_today=today_values["count"], revenue_today=today_values["total"],
            sales_month=month_values["total"], average_ticket=(total / count).quantize(Decimal("0.01")) if count else Decimal("0"),
            sales_count=count,
            pending_orders=self._orders.count_documents({"status": {"$in": ["aguardando_pagamento", "pago", "em_separacao"]}}),
            pending_deliveries=self._deliveries.count_documents({"status": {"$nin": ["entregue", "cancelado", "nao_entregue"]}}),
            current_cash=_decimal(open_cash.get("saldo_esperado")),
            cash_sales=payments.get("dinheiro", Decimal("0")), pix_sales=payments.get("pix", Decimal("0")),
            debit_sales=payments.get("debito", Decimal("0")), credit_sales=payments.get("credito", Decimal("0")) + payments.get("credito_parcelado", Decimal("0")),
            expenses=expenses, estimated_profit=total - _decimal(values.get("cost")) - expenses,
            low_stock_products=self._products.count_documents({"ativo": True, "$expr": {"$lte": ["$estoque_atual_unidades", "$estoque_minimo"]}}),
            expiring_products=self._products.count_documents({"ativo": True, "data_validade": {"$gte": today, "$lte": today + timedelta(days=30)}}),
            credit_total=_decimal(credit_open[0].get("total")) if credit_open else Decimal("0"), credit_overdue=_decimal(credit_overdue[0].get("total")) if credit_overdue else Decimal("0"), credit_received_today=credit_today, credit_received_month=credit_month, credit_delinquent_customers=len(credit_overdue[0].get("customers",[])) if credit_overdue else 0, credit_near_limit_customers=self._customers.count_documents({"fiado_habilitado": True, "$expr": {"$gte": ["$fiado_saldo_devedor", {"$multiply": ["$fiado_limite_credito", Decimal128(Decimal("0.80"))]}]}}),
            command_open=len(active_commands),command_open_value=sum((_decimal(x.get("total")) for x in active_commands),Decimal("0")),command_awaiting=sum(x.get("status")=="aguardando_pagamento" for x in active_commands),command_finalized_today=self._commands.count_documents({"status":"finalizada","data_fechamento":{"$gte":today}}),command_oldest_minutes=int((datetime.now(timezone.utc)-oldest).total_seconds()//60) if oldest else 0,
            sales_by_day=self._chart_group(match, {"$dateToString": {"format": "%d/%m", "date": "$data_hora", "timezone": "UTC"}}, "$total"),
            sales_by_month=self._chart_group(match, {"$dateToString": {"format": "%m/%Y", "date": "$data_hora", "timezone": "UTC"}}, "$total"),
            sales_by_category=self._item_group(match, "itens.categoria_nome"),
            top_products=self._item_group(match, "itens.produto_nome"),
            payment_methods=[ChartPoint(label=key.title(), value=value) for key, value in payments.items()],
            package_sales=self._item_group(match, "itens.tipo_embalagem"),
            **self._profitability_series(match),
        )

    def _sum_sales(self, start: datetime, end: datetime) -> dict[str, Any]:
        rows = list(self._sales.aggregate([{"$match": {"data_hora": {"$gte": start, "$lt": end}, "status": {"$in": ["concluida", "finalizada", "paga"]}}}, {"$group": {"_id": None, "total": {"$sum": "$total"}, "count": {"$sum": 1}}}]))
        return {"total": _decimal(rows[0].get("total")) if rows else Decimal("0"), "count": int(rows[0].get("count", 0)) if rows else 0}

    @staticmethod
    def _sum_collection(collection, field: str, start: datetime, end: datetime) -> Decimal:
        rows = list(collection.aggregate([{"$match": {"data_hora": {"$gte": start, "$lt": end}, "status": {"$ne": "cancelada"}}}, {"$group": {"_id": None, "total": {"$sum": f"${field}"}}}]))
        return _decimal(rows[0].get("total")) if rows else Decimal("0")

    def _sum_credit_payments(self, start: datetime, end: datetime) -> Decimal:
        rows = list(self._credit_payments.aggregate([
            {"$match": {"data_hora": {"$gte": start, "$lt": end}, "estornado": {"$ne": True}}},
            {"$group": {"_id": None, "total": {"$sum": "$valor"}}},
        ]))
        return _decimal(rows[0].get("total")) if rows else Decimal("0")

    def _group_payments(self, match: dict[str, Any]) -> dict[str, Decimal]:
        rows = self._sales.aggregate([{"$match": match}, {"$unwind": "$pagamentos"}, {"$group": {"_id": "$pagamentos.forma", "total": {"$sum": "$pagamentos.valor"}}}])
        return {str(row["_id"]): _decimal(row["total"]) for row in rows if row.get("_id")}

    def _chart_group(self, match: dict[str, Any], group_id: Any, value: str) -> list[ChartPoint]:
        rows = self._sales.aggregate([{"$match": match}, {"$group": {"_id": group_id, "total": {"$sum": value}}}, {"$sort": {"_id": 1}}])
        return [ChartPoint(label=str(row["_id"]), value=_decimal(row["total"])) for row in rows]

    def _item_group(self, match: dict[str, Any], field: str) -> list[ChartPoint]:
        rows = self._sales.aggregate([{"$match": match}, {"$unwind": "$itens"}, {"$group": {"_id": f"${field}", "total": {"$sum": "$itens.quantidade"}}}, {"$sort": {"total": -1}}, {"$limit": 10}])
        return [ChartPoint(label=str(row["_id"] or "Não informado").title(), value=_decimal(row["total"])) for row in rows]

    def _profitability_series(self, match: dict[str, Any]) -> dict[str, list[ChartPoint]]:
        rows = self._sales.aggregate([
            {"$match": match},
            {"$group": {
                "_id": {"$dateToString": {"format": "%d/%m", "date": "$data_hora", "timezone": "UTC"}},
                "revenue": {"$sum": "$total"}, "cost": {"$sum": "$custo_total"},
            }},
            {"$sort": {"_id": 1}},
        ])
        revenue: list[ChartPoint] = []
        cost: list[ChartPoint] = []
        profit: list[ChartPoint] = []
        for row in rows:
            revenue_value = _decimal(row.get("revenue"))
            cost_value = _decimal(row.get("cost"))
            label = str(row["_id"])
            revenue.append(ChartPoint(label=label, value=revenue_value))
            cost.append(ChartPoint(label=label, value=cost_value))
            profit.append(ChartPoint(label=label, value=revenue_value - cost_value))
        return {"revenue_series": revenue, "cost_series": cost, "profit_series": profit}
