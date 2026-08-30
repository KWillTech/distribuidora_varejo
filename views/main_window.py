"""Janela principal com navegação lateral, topo e temas."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton, QStackedWidget, QVBoxLayout, QWidget

from models.auth import AuthenticatedSession, Permission
from services.dashboard import DashboardService
from services.customers import CustomerService
from services.users import UserService
from services.suppliers import SupplierService
from services.catalog import CatalogService
from services.packaging import PackagingService
from services.stock import StockService
from services.purchases import PurchaseService
from services.sales import SaleService
from services.cash import CashService
from services.orders import OrderService
from services.finance import FinanceService
from services.reports import ReportService
from services.administration import AdministrationService
from services.credit import CreditService
from services.commands import CommandService
from views.dashboard_view import DashboardView
from views.customers_view import CustomersView
from views.user_management_view import UserManagementWindow
from views.suppliers_view import SuppliersView
from views.catalog_view import CatalogView
from views.stock_view import StockView
from views.purchases_view import PurchasesView
from views.pos_view import PosView
from views.cash_view import CashView
from views.orders_view import OrdersView
from views.finance_view import FinanceView
from views.reports_view import ReportsView
from views.administration_view import AdministrationView
from views.credit_view import CreditView
from views.commands_view import CommandsView
from utils.resources import logo_pixmap


class MainWindow(QMainWindow):
    logout_requested = Signal()

    def __init__(self, session: AuthenticatedSession, dashboard_service: DashboardService, user_service: UserService, customer_service: CustomerService, supplier_service: SupplierService, catalog_service: CatalogService, packaging_service: PackagingService, stock_service: StockService, purchase_service: PurchaseService, sale_service: SaleService | None = None, cash_service: CashService | None = None, order_service: OrderService | None = None, finance_service: FinanceService | None = None, report_service: ReportService | None = None, administration_service: AdministrationService | None = None,credit_service:CreditService|None=None,command_service:CommandService|None=None) -> None:
        super().__init__()
        self.session = session
        self._settings = QSettings("DistribuidoraVarejo", "DistribuidoraVarejo")
        self._expanded = True
        self.setWindowTitle("Distribuidora Varejo")
        self.resize(1360, 800)
        root = QWidget(); root_layout = QHBoxLayout(root); root_layout.setContentsMargins(0, 0, 0, 0); root_layout.setSpacing(0)
        self.sidebar = QFrame(); self.sidebar.setObjectName("sidebar"); self.sidebar.setFixedWidth(230)
        side_layout = QVBoxLayout(self.sidebar)
        side_layout.setContentsMargins(8, 10, 8, 10); side_layout.setSpacing(3)
        self.brand = QLabel(); self.brand.setObjectName("brand"); self.brand.setAlignment(Qt.AlignmentFlag.AlignCenter); self.brand.setPixmap(logo_pixmap(175, 125)); side_layout.addWidget(self.brand)
        self.nav_group = QButtonGroup(self); self.nav_group.setExclusive(True); self.section_labels = []
        self.dashboard_button = self._nav_button("📊  Painel", "📊")
        if Permission.DASHBOARD_VIEW not in session.permissions: self.dashboard_button.hide()
        self.dashboard_button.clicked.connect(lambda: self._navigate(0, self.dashboard_button))
        self.users_button = self._nav_button("👥  Usuários", "👥")
        if Permission.USERS_VIEW not in session.permissions: self.users_button.hide()
        self.users_button.clicked.connect(lambda: self._navigate(1, self.users_button))
        self.customers_button = self._nav_button("👤  Clientes", "👤")
        if Permission.CUSTOMERS_VIEW not in session.permissions: self.customers_button.hide()
        self.customers_button.clicked.connect(lambda: self._navigate(2, self.customers_button))
        self.suppliers_button = self._nav_button("🏭  Fornecedores", "🏭")
        if Permission.SUPPLIERS_VIEW not in session.permissions: self.suppliers_button.hide()
        self.suppliers_button.clicked.connect(lambda: self._navigate(3, self.suppliers_button))
        self.catalog_button = self._nav_button("🍺  Produtos", "🍺")
        if Permission.PRODUCTS_VIEW not in session.permissions: self.catalog_button.hide()
        self.catalog_button.clicked.connect(lambda: self._navigate(4, self.catalog_button))
        self.stock_button = self._nav_button("📦  Estoque", "📦")
        if Permission.STOCK_VIEW not in session.permissions: self.stock_button.hide()
        self.stock_button.clicked.connect(lambda: self._navigate(5, self.stock_button))
        self.purchases_button = self._nav_button("🧾  Compras", "🧾")
        if Permission.PURCHASES_CREATE not in session.permissions: self.purchases_button.hide()
        self.purchases_button.clicked.connect(lambda: self._navigate(6, self.purchases_button))
        self.pos_button = self._nav_button("🛒  PDV", "🛒")
        if Permission.POS_ACCESS not in session.permissions: self.pos_button.hide()
        self.pos_button.clicked.connect(lambda: self._navigate(7, self.pos_button))
        self.cash_button = self._nav_button("💰  Caixa", "💰")
        cash_permissions = {Permission.CASH_OPEN, Permission.CASH_WITHDRAW, Permission.CASH_CLOSE}
        if not (cash_permissions & session.permissions): self.cash_button.hide()
        self.cash_button.clicked.connect(lambda: self._navigate(8, self.cash_button))
        self.orders_button = self._nav_button("🚚  Pedidos e entregas", "🚚")
        delivery_permissions = {Permission.DELIVERIES_MANAGE, Permission.DELIVERIES_OWN, Permission.ORDERS_CREATE}
        if not (delivery_permissions & session.permissions): self.orders_button.hide()
        self.orders_button.clicked.connect(lambda: self._navigate(9, self.orders_button))
        self.finance_button = self._nav_button("💳  Financeiro", "💳")
        if Permission.FINANCE_VIEW not in session.permissions:self.finance_button.hide()
        self.finance_button.clicked.connect(lambda:self._navigate(10,self.finance_button))
        self.reports_button=self._nav_button("📈  Relatórios","📈")
        if Permission.REPORTS_VIEW not in session.permissions:self.reports_button.hide()
        self.reports_button.clicked.connect(lambda:self._navigate(11,self.reports_button))
        self.admin_button=self._nav_button("⚙️  Administração","⚙️")
        admin_permissions={Permission.AUDIT_VIEW,Permission.SETTINGS_MANAGE,Permission.BACKUP_CREATE,Permission.BACKUP_RESTORE}
        if not (admin_permissions&session.permissions):self.admin_button.hide()
        self.admin_button.clicked.connect(lambda:self._navigate(12,self.admin_button))
        self.credit_button=self._nav_button("🤝  Fiado","🤝")
        if Permission.CREDIT_VIEW not in session.permissions:self.credit_button.hide()
        self.credit_button.clicked.connect(lambda:self._navigate(13,self.credit_button))
        self.commands_button=self._nav_button("📋  Comandas","📋")
        if Permission.TABS_VIEW not in session.permissions:self.commands_button.hide()
        self.commands_button.clicked.connect(lambda:self._navigate(14,self.commands_button))
        self._add_menu_section(side_layout, "GERAL", (self.dashboard_button,))
        self._add_menu_section(side_layout, "ATENDIMENTO", (self.pos_button,self.commands_button, self.customers_button,self.credit_button, self.orders_button))
        self._add_menu_section(side_layout, "GESTÃO", (self.cash_button, self.stock_button, self.purchases_button, self.finance_button, self.reports_button))
        self._add_menu_section(side_layout, "CADASTROS", (self.catalog_button, self.suppliers_button, self.users_button))
        self._add_menu_section(side_layout, "SISTEMA", (self.admin_button,))
        side_layout.addStretch()
        self.collapse_button = self._nav_button("≪  Recolher", "≫", navigation=False)
        self.collapse_button.clicked.connect(self._toggle_sidebar); side_layout.addWidget(self.collapse_button)
        root_layout.addWidget(self.sidebar)
        content = QWidget(); content_layout = QVBoxLayout(content); content_layout.setContentsMargins(0, 0, 0, 0)
        top = QFrame(); top.setObjectName("topbar"); top_layout = QHBoxLayout(top)
        top_layout.addStretch()
        top_layout.addWidget(QLabel(f"{session.user.full_name}  •  {session.user.profile_code.value.title()}"))
        self.theme_button = QPushButton("☾ Tema escuro"); self.theme_button.clicked.connect(self._toggle_theme); top_layout.addWidget(self.theme_button)
        logout = QPushButton("↪  Sair"); logout.clicked.connect(self.logout_requested.emit); top_layout.addWidget(logout)
        content_layout.addWidget(top)
        self.pages = QStackedWidget()
        if Permission.DASHBOARD_VIEW in session.permissions:
            dashboard_page = DashboardView(session, dashboard_service, self.pages)
        else:
            dashboard_page = QLabel("Nenhum painel liberado para este perfil.")
            dashboard_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pages.addWidget(dashboard_page)
        self.pages.addWidget(UserManagementWindow(session, user_service, self.pages))
        if Permission.CUSTOMERS_VIEW in session.permissions:
            customers_page = CustomersView(session, customer_service, self.pages)
        else:
            customers_page = QLabel("Acesso ao cadastro de clientes não liberado.")
            customers_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pages.addWidget(customers_page)
        if Permission.SUPPLIERS_VIEW in session.permissions:
            suppliers_page = SuppliersView(session, supplier_service, self.pages)
        else:
            suppliers_page = QLabel("Acesso ao cadastro de fornecedores não liberado.")
            suppliers_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pages.addWidget(suppliers_page)
        if Permission.PRODUCTS_VIEW in session.permissions:
            catalog_page = CatalogView(session, catalog_service, packaging_service, self.pages)
        else:
            catalog_page = QLabel("Acesso ao catálogo de produtos não liberado.")
            catalog_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pages.addWidget(catalog_page)
        if Permission.STOCK_VIEW in session.permissions:
            stock_page = StockView(session, stock_service, catalog_service, purchase_service, self.pages)
        else:
            stock_page = QLabel("Acesso ao estoque não liberado.")
            stock_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pages.addWidget(stock_page)
        if Permission.PURCHASES_CREATE in session.permissions:
            purchases_page = PurchasesView(session, purchase_service, supplier_service, catalog_service, self.pages)
        else:
            purchases_page = QLabel("Acesso ao módulo de compras não liberado.")
            purchases_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pages.addWidget(purchases_page)
        if Permission.POS_ACCESS in session.permissions and sale_service is not None:
            pos_page = PosView(session, catalog_service, sale_service, self.pages,customer_service,credit_service,command_service)
        else:
            pos_page = QLabel("Acesso ao PDV não liberado."); pos_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pages.addWidget(pos_page)
        if cash_service is not None and cash_permissions & session.permissions: cash_page = CashView(session, cash_service, self.pages)
        else: cash_page = QLabel("Acesso ao caixa não liberado."); cash_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pages.addWidget(cash_page)
        if order_service is not None and delivery_permissions & session.permissions: orders_page = OrdersView(session, order_service, self.pages)
        else: orders_page = QLabel("Acesso a pedidos e entregas não liberado."); orders_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pages.addWidget(orders_page)
        if finance_service is not None and Permission.FINANCE_VIEW in session.permissions:finance_page=FinanceView(session,finance_service,self.pages)
        else:finance_page=QLabel("Acesso ao financeiro não liberado."); finance_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pages.addWidget(finance_page)
        if report_service is not None and Permission.REPORTS_VIEW in session.permissions:report_page=ReportsView(session,report_service,self.pages)
        else:report_page=QLabel("Acesso aos relatórios não liberado."); report_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pages.addWidget(report_page)
        if administration_service is not None and admin_permissions&session.permissions:admin_page=AdministrationView(session,administration_service,self.pages)
        else:admin_page=QLabel("Acesso à administração não liberado."); admin_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pages.addWidget(admin_page)
        if credit_service is not None and Permission.CREDIT_VIEW in session.permissions:credit_page=CreditView(session,credit_service,customer_service,self.pages)
        else:credit_page=QLabel("Acesso ao fiado não liberado."); credit_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pages.addWidget(credit_page)
        if command_service is not None and Permission.TABS_VIEW in session.permissions:commands_page=CommandsView(session,command_service,catalog_service,customer_service,credit_service,self.pages)
        else:commands_page=QLabel("Acesso às comandas não liberado."); commands_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pages.addWidget(commands_page)
        visible_navigation = ((0, self.dashboard_button),(11,self.reports_button), (7, self.pos_button),(14,self.commands_button),(13,self.credit_button), (8, self.cash_button), (9, self.orders_button), (10,self.finance_button),(6, self.purchases_button), (5, self.stock_button), (4, self.catalog_button), (2, self.customers_button), (3, self.suppliers_button), (1, self.users_button),(12,self.admin_button))
        for index, button in visible_navigation:
            if not button.isHidden(): self.pages.setCurrentIndex(index); button.setChecked(True); break
        content_layout.addWidget(self.pages)
        root_layout.addWidget(content, 1)
        self.setCentralWidget(root)
        self._dark = self._settings.value("dark_theme", False, type=bool)
        self._apply_theme()

    def _nav_button(self, expanded: str, collapsed: str, navigation: bool = True) -> QPushButton:
        button = QPushButton(expanded); button.setProperty("expandedText", expanded); button.setProperty("collapsedText", collapsed); button.setProperty("collapsed", False); button.setObjectName("navButton"); button.setCheckable(navigation)
        if navigation: self.nav_group.addButton(button)
        return button

    def _add_menu_section(self, layout: QVBoxLayout, title: str, buttons: tuple[QPushButton, ...]) -> None:
        label = QLabel(title); label.setObjectName("menuSection"); self.section_labels.append(label); layout.addWidget(label)
        for button in buttons: layout.addWidget(button)

    def _navigate(self, index: int, button: QPushButton) -> None:
        self.pages.setCurrentIndex(index); button.setChecked(True)

    def _toggle_sidebar(self) -> None:
        self._expanded = not self._expanded
        self.sidebar.setFixedWidth(230 if self._expanded else 68)
        self.brand.setPixmap(logo_pixmap(175, 125) if self._expanded else logo_pixmap(54, 54))
        for label in self.section_labels: label.setVisible(self._expanded)
        for button in (self.dashboard_button, self.users_button, self.customers_button, self.suppliers_button, self.catalog_button, self.stock_button, self.purchases_button, self.pos_button,self.commands_button, self.cash_button, self.orders_button,self.finance_button,self.reports_button,self.admin_button,self.credit_button, self.collapse_button):
            button.setText(button.property("expandedText") if self._expanded else button.property("collapsedText")); button.setProperty("collapsed", not self._expanded); button.style().unpolish(button); button.style().polish(button)

    def _toggle_theme(self) -> None:
        self._dark = not self._dark
        self._settings.setValue("dark_theme", self._dark)
        self._settings.sync()
        self._apply_theme()

    @property
    def dark_theme(self) -> bool:
        return self._dark

    def _apply_theme(self) -> None:
        style_name = "dark.qss" if self._dark else "app.qss"
        stylesheet = Path(__file__).resolve().parent.parent / "resources" / "styles" / style_name
        self.setStyleSheet(stylesheet.read_text(encoding="utf-8"))
        self.theme_button.setText("☀ Tema claro" if self._dark else "☾ Tema escuro")
