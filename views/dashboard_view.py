"""Dashboard responsivo com filtros, cards e gráficos QtCharts."""

from __future__ import annotations

from datetime import datetime, time, timezone
from decimal import Decimal

from PySide6.QtCharts import QBarCategoryAxis, QBarSeries, QBarSet, QChart, QChartView, QLineSeries, QPieSeries, QValueAxis
from PySide6.QtCore import QDate, QObject, QRunnable, QThreadPool, Qt, Signal, Slot
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QComboBox, QDateEdit, QFormLayout, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget

from models.auth import AuthenticatedSession,Permission
from models.dashboard import DashboardData, DashboardFilter
from services.dashboard import DashboardService
from widgets.metric_card import MetricCard


def brl(value: Decimal) -> str:
    text = f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {text}"


class WorkerSignals(QObject):
    succeeded = Signal(object)
    failed = Signal(str)


class DashboardWorker(QRunnable):
    def __init__(self, service: DashboardService, session: AuthenticatedSession, filters: DashboardFilter) -> None:
        super().__init__()
        self.service = service
        self.session = session
        self.filters = filters
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            self.signals.succeeded.emit(self.service.load(self.session, self.filters))
        except Exception as exc:
            self.signals.failed.emit(str(exc))


class DashboardView(QWidget):
    CARD_FIELDS = (
        ("sales_today", "Vendas do dia", False), ("revenue_today", "Receita do dia", True),
        ("sales_month", "Vendas do mês", True),
        ("pending_orders", "Pedidos pendentes", False),
        ("pending_deliveries", "Entregas pendentes", False), ("current_cash", "Caixa atual", True),
        ("cash_sales", "Vendas em dinheiro", True), ("pix_sales", "Vendas em Pix", True),
        ("debit_sales", "Vendas em débito", True), ("credit_sales", "Vendas em crédito", True),
        ("expenses", "Despesas", True),
        ("low_stock_products", "Estoque baixo", False), ("expiring_products", "Próximos do vencimento", False),
        ("credit_total","Total a receber em fiado",True),("credit_overdue","Fiado vencido",True),("credit_received_today","Fiado recebido hoje",True),("credit_delinquent_customers","Clientes inadimplentes",False),
        ("command_open","Comandas abertas",False),("command_open_value","Valor em comandas",True),("command_awaiting","Comandas aguardando",False),("command_finalized_today","Comandas finalizadas hoje",False),
    )

    def __init__(self, session: AuthenticatedSession, service: DashboardService, parent=None) -> None:
        super().__init__(parent)
        self.session = session
        self.service = service
        self.thread_pool = QThreadPool.globalInstance()
        self.cards: dict[str, MetricCard] = {}
        self.card_fields=[item for item in self.CARD_FIELDS if (not item[0].startswith("credit_") or Permission.CREDIT_VIEW in session.permissions) and (not item[0].startswith("command_") or Permission.TABS_VIEW in session.permissions)]
        self._workers: set[DashboardWorker] = set()
        root = QVBoxLayout(self)
        title = QLabel("Painel")
        title.setObjectName("pageTitle")
        root.addWidget(title)
        root.addWidget(self._build_filters())
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        cards = QGridLayout()
        for index, (field, label, _) in enumerate(self.card_fields):
            card = MetricCard(label)
            self.cards[field] = card
            cards.addWidget(card, index // 4, index % 4)
        content_layout.addLayout(cards)
        charts = QGridLayout()
        self.daily_chart = QChartView()
        self.monthly_chart = QChartView()
        self.category_chart = QChartView()
        self.products_chart = QChartView()
        self.payment_chart = QChartView()
        self.package_chart = QChartView()
        self.profit_chart = QChartView()
        for view in (self.daily_chart, self.monthly_chart, self.category_chart, self.products_chart, self.payment_chart, self.package_chart, self.profit_chart):
            view.setRenderHint(QPainter.RenderHint.Antialiasing)
            view.setMinimumHeight(280)
        charts.addWidget(self.daily_chart, 0, 0)
        charts.addWidget(self.monthly_chart, 0, 1)
        charts.addWidget(self.category_chart, 1, 0)
        charts.addWidget(self.products_chart, 1, 1)
        charts.addWidget(self.payment_chart, 2, 0)
        charts.addWidget(self.package_chart, 2, 1)
        charts.addWidget(self.profit_chart, 3, 0, 1, 2)
        content_layout.addLayout(charts)
        scroll.setWidget(content)
        root.addWidget(scroll)
        self.refresh()

    def _build_filters(self) -> QWidget:
        panel = QWidget()
        layout = QHBoxLayout(panel)
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDisplayFormat("dd/MM/yyyy")
        self.start_date.setDate(QDate.currentDate().addDays(-29))
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDisplayFormat("dd/MM/yyyy")
        self.end_date.setDate(QDate.currentDate())
        self.user_filter = QLineEdit(); self.user_filter.setPlaceholderText("ID do usuário")
        self.product_filter = QLineEdit(); self.product_filter.setPlaceholderText("ID do produto")
        self.category_filter = QLineEdit(); self.category_filter.setPlaceholderText("ID da categoria")
        self.payment_filter = QComboBox(); self.payment_filter.addItems(["Todas", "Dinheiro", "Pix", "Débito", "Crédito", "Crédito parcelado"])
        self.package_filter = QComboBox(); self.package_filter.addItems(["Todos", "Unidade", "Fardo"])
        for label, widget in (("De", self.start_date), ("Até", self.end_date), ("Usuário", self.user_filter), ("Produto", self.product_filter), ("Categoria", self.category_filter), ("Pagamento", self.payment_filter), ("Venda", self.package_filter)):
            form = QFormLayout(); form.addRow(label, widget); layout.addLayout(form)
        self.refresh_button = QPushButton("Atualizar")
        self.refresh_button.clicked.connect(self.refresh)
        layout.addWidget(self.refresh_button)
        return panel

    def _filters(self) -> DashboardFilter:
        start = datetime.combine(self.start_date.date().toPython(), time.min, tzinfo=timezone.utc)
        end = datetime.combine(self.end_date.date().toPython(), time.max, tzinfo=timezone.utc)
        payment = self.payment_filter.currentText().lower().replace("é", "e").replace(" ", "_")
        package = self.package_filter.currentText().lower()
        return DashboardFilter(
            start_date=start, end_date=end, user_id=self.user_filter.text().strip() or None,
            product_id=self.product_filter.text().strip() or None, category_id=self.category_filter.text().strip() or None,
            payment_method=None if self.payment_filter.currentIndex() == 0 else payment,
            package_type=None if self.package_filter.currentIndex() == 0 else package,
        )

    @Slot()
    def refresh(self) -> None:
        try:
            filters = self._filters()
        except ValueError as exc:
            QMessageBox.warning(self, "Filtro inválido", str(exc))
            return
        self.refresh_button.setEnabled(False)
        self.refresh_button.setText("Carregando…")
        worker = DashboardWorker(self.service, self.session, filters)
        self._workers.add(worker)
        worker.signals.succeeded.connect(lambda data, item=worker: self._loaded(item, data))
        worker.signals.failed.connect(lambda message, item=worker: self._failed(item, message))
        self.thread_pool.start(worker)

    def _loaded(self, worker: DashboardWorker, data: DashboardData) -> None:
        self._workers.discard(worker)
        self.refresh_button.setEnabled(True); self.refresh_button.setText("Atualizar")
        for field, _, monetary in self.card_fields:
            value = getattr(data, field)
            self.cards[field].set_value(brl(Decimal(value)) if monetary else str(value))
        self.daily_chart.setChart(self._line_chart("Vendas por dia", data.sales_by_day))
        self.monthly_chart.setChart(self._line_chart("Vendas por mês", data.sales_by_month))
        self.category_chart.setChart(self._bar_chart("Vendas por categoria", data.sales_by_category))
        self.products_chart.setChart(self._bar_chart("Produtos mais vendidos", data.top_products))
        self.payment_chart.setChart(self._pie_chart("Formas de pagamento", data.payment_methods))
        self.package_chart.setChart(self._bar_chart("Unidade x fardo", data.package_sales))
        self.profit_chart.setChart(self._multi_line_chart("Receita, custo e lucro", data.revenue_series, data.cost_series, data.profit_series))

    def _failed(self, worker: DashboardWorker, message: str) -> None:
        self._workers.discard(worker)
        self.refresh_button.setEnabled(True); self.refresh_button.setText("Atualizar")
        QMessageBox.warning(self, "Dashboard indisponível", message)

    @staticmethod
    def _empty_chart(title: str) -> QChart:
        chart = QChart(); chart.setTitle(title); chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        chart.setBackgroundBrush(QColor("#171717"))
        chart.setPlotAreaBackgroundBrush(QColor("#171717")); chart.setPlotAreaBackgroundVisible(True)
        chart.setTitleBrush(QColor("#ffc23d")); chart.legend().setLabelColor(QColor("#f7f2e8"))
        return chart

    def _line_chart(self, title: str, points) -> QChart:
        chart = self._empty_chart(title)
        series = QLineSeries()
        series.setPen(QPen(QColor("#ff8a00"), 3))
        for index, point in enumerate(points): series.append(index, float(point.value))
        chart.addSeries(series)
        if points:
            axis_x = QBarCategoryAxis(); axis_x.append([p.label for p in points]); axis_x.setLabelsBrush(QColor("#f7f2e8")); chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom); series.attachAxis(axis_x)
            axis_y = QValueAxis(); axis_y.setLabelFormat("%.0f"); axis_y.setLabelsBrush(QColor("#f7f2e8")); chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft); series.attachAxis(axis_y)
        return chart

    def _bar_chart(self, title: str, points) -> QChart:
        chart = self._empty_chart(title)
        values = QBarSet("Total"); values.setColor(QColor("#f5a400")); values.setBorderColor(QColor("#ff6a00")); values.append([float(p.value) for p in points])
        series = QBarSeries(); series.append(values); chart.addSeries(series)
        if points:
            axis = QBarCategoryAxis(); axis.append([p.label for p in points]); axis.setLabelsBrush(QColor("#f7f2e8")); chart.addAxis(axis, Qt.AlignmentFlag.AlignBottom); series.attachAxis(axis)
            axis_y = QValueAxis(); axis_y.setLabelsBrush(QColor("#f7f2e8")); chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft); series.attachAxis(axis_y)
        return chart

    def _pie_chart(self, title: str, points) -> QChart:
        chart = self._empty_chart(title)
        series = QPieSeries()
        colors = ("#f5a400", "#ff6a00", "#ffd45e", "#f0f0f0", "#a85a00", "#8c8c8c")
        for index, point in enumerate(points):
            pie_slice = series.append(point.label, float(point.value)); pie_slice.setColor(QColor(colors[index % len(colors)])); pie_slice.setLabelColor(QColor("#f7f2e8"))
        chart.addSeries(series)
        return chart

    def _multi_line_chart(self, title: str, revenue, cost, profit) -> QChart:
        chart = self._empty_chart(title)
        series_list = []
        for (name, points), color in zip((("Receita", revenue), ("Custo", cost), ("Lucro", profit)), ("#f5a400", "#f2f2f2", "#ff6a00"), strict=True):
            series = QLineSeries(); series.setName(name)
            series.setPen(QPen(QColor(color), 3))
            for index, point in enumerate(points): series.append(index, float(point.value))
            chart.addSeries(series); series_list.append(series)
        if revenue:
            axis_x = QBarCategoryAxis(); axis_x.append([p.label for p in revenue]); axis_x.setLabelsBrush(QColor("#f7f2e8")); chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
            axis_y = QValueAxis(); axis_y.setLabelFormat("%.0f"); axis_y.setLabelsBrush(QColor("#f7f2e8")); chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
            for series in series_list: series.attachAxis(axis_x); series.attachAxis(axis_y)
        return chart
