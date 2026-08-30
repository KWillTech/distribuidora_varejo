"""Ponto de entrada gráfico da aplicação Distribuidora Varejo."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from config.database import MongoDatabase
from config.settings import SettingsError, get_settings
from controllers.auth_controller import AuthController
from dialogs.password_dialog import PasswordChangeDialog
from models.auth import AuthenticatedSession
from repositories.auth import AuditRepository, ProfileRepository, UserRepository
from repositories.dashboard import DashboardRepository
from repositories.customers import CustomerRepository
from repositories.suppliers import SupplierRepository
from repositories.catalog import CategoryRepository, ProductRepository
from services.authentication import AuthenticationService
from services.bootstrap import seed_authentication
from services.dashboard import DashboardService
from services.customers import CustomerService
from services.suppliers import SupplierService
from services.catalog import CatalogService
from services.catalog_bootstrap import seed_categories
from services.packaging import PackagingService
from services.stock import StockService
from repositories.stock import StockRepository
from repositories.purchases import PurchaseRepository
from repositories.sales import SaleRepository
from repositories.cash import CashRepository
from repositories.orders import OrderRepository
from repositories.finance import FinanceRepository
from repositories.reports import ReportRepository
from repositories.administration import AdministrationRepository
from repositories.credit import CreditRepository
from repositories.commands import CommandRepository
from services.purchases import PurchaseService
from services.sales import SaleService
from services.cash import CashService
from services.orders import OrderService
from services.finance import FinanceService
from services.reports import ReportService
from services.administration import AdministrationService
from services.credit import CreditService
from services.commands import CommandService
from services.users import UserService
from utils.logging_config import configure_logging, get_logger
from utils.resources import LOGO_PATH, logo_pixmap
from views.login_view import LoginView
from views.main_window import MainWindow


class ApplicationCoordinator:
    """Coordena janelas e serviços sem acesso das views ao MongoDB."""

    def __init__(self, app: QApplication, database: MongoDatabase) -> None:
        self.app = app
        self.database = database
        users = UserRepository(database.database)
        profiles = ProfileRepository(database.database)
        audit = AuditRepository(database.database)
        generated_password = seed_authentication(
            users, profiles, audit, get_settings().initial_admin_password
        )
        if generated_password:
            QMessageBox.information(
                None,
                "Administrador inicial",
                "Usuário: admin\n"
                f"Senha temporária: {generated_password}\n\n"
                "Anote agora. Ela será exibida somente nesta inicialização.",
            )
        self.auth_service = AuthenticationService(users, profiles, audit)
        self.user_service = UserService(users, audit)
        self.dashboard_service = DashboardService(DashboardRepository(database.database))
        self.customer_service = CustomerService(CustomerRepository(database.database), audit)
        self.supplier_service = SupplierService(SupplierRepository(database.database), audit)
        category_repository = CategoryRepository(database.database)
        seed_categories(category_repository)
        self.catalog_service = CatalogService(category_repository, ProductRepository(database.database), audit)
        self.packaging_service = PackagingService(ProductRepository(database.database), audit)
        self.stock_service = StockService(StockRepository(database.database), audit)
        self.purchase_service = PurchaseService(PurchaseRepository(database.database), ProductRepository(database.database), self.stock_service, audit)
        self.cash_service = CashService(CashRepository(database.database), audit)
        self.credit_service = CreditService(CreditRepository(database.database),audit,self.cash_service)
        self.sale_service = SaleService(SaleRepository(database.database), self.stock_service, audit, self.cash_service,self.credit_service)
        self.command_service = CommandService(CommandRepository(database.database),audit,self.sale_service)
        self.order_service = OrderService(OrderRepository(database.database), audit)
        self.finance_service = FinanceService(FinanceRepository(database.database), audit)
        self.report_service = ReportService(ReportRepository(database.database), audit)
        self.administration_service = AdministrationService(AdministrationRepository(database.database), audit)
        self.auth_controller = AuthController(self.auth_service)
        self.login_view = LoginView(get_settings().app_name)
        self.main_window: MainWindow | None = None
        self.password_dialog: PasswordChangeDialog | None = None
        self._pending_session: AuthenticatedSession | None = None
        self._current_session: AuthenticatedSession | None = None
        self.auth_controller.login_succeeded.connect(self._on_login)
        self.auth_controller.login_failed.connect(self.login_view.show_error)
        self.login_view.login_requested.connect(self.auth_controller.login)
        self.app.aboutToQuit.connect(self._shutdown)
        self.app.aboutToQuit.connect(self.database.close)

    def start(self) -> None:
        self.login_view.show()

    def _on_login(self, session: AuthenticatedSession) -> None:
        self._pending_session = session
        if session.user.must_change_password:
            self.password_dialog = PasswordChangeDialog(
                mandatory=True, parent=self.login_view
            )
            self.password_dialog.submitted.connect(
                lambda current, new: self.auth_controller.change_password(
                    session, current, new
                )
            )
            self.auth_controller.password_changed.connect(self._password_changed)
            self.auth_controller.password_change_failed.connect(
                self.password_dialog.show_error
            )
            self.password_dialog.show()
            return
        self._open_main(session)

    def _password_changed(self) -> None:
        if self.password_dialog:
            self.password_dialog.accept()
        if self._pending_session:
            self._open_main(self._pending_session)

    def _open_main(self, session: AuthenticatedSession) -> None:
        self.login_view.set_loading(True)
        self._current_session = session
        self.main_window = MainWindow(
            session, self.dashboard_service, self.user_service, self.customer_service, self.supplier_service, self.catalog_service, self.packaging_service, self.stock_service, self.purchase_service, self.sale_service, self.cash_service, self.order_service, self.finance_service, self.report_service, self.administration_service,self.credit_service,self.command_service
        )
        self.main_window.logout_requested.connect(self._logout)
        self.main_window.showMaximized()
        self.main_window.raise_()
        QTimer.singleShot(80, self._finish_login_transition)

    def _finish_login_transition(self) -> None:
        if self.main_window:
            self.main_window.activateWindow(); self.main_window.raise_()
        self.login_view.hide(); self.login_view.set_loading(False)

    def _logout(self) -> None:
        selected_dark_theme = self.main_window.dark_theme if self.main_window else None
        if self._current_session:
            self.auth_controller.logout(self._current_session)
            self._current_session = None
        if self.main_window:
            self.main_window.close()
            self.main_window = None
        self.login_view.password_input.clear()
        self.login_view.login_button.setEnabled(True)
        self.login_view.set_loading(False)
        if selected_dark_theme is None: self.login_view.apply_saved_theme()
        else: self.login_view.apply_theme(selected_dark_theme)
        self.login_view.show()

    def _shutdown(self) -> None:
        if self._current_session:
            self.auth_controller.logout(self._current_session)
            self._current_session = None


def main() -> int:
    """Inicializa infraestrutura, autenticação e interface Qt."""
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Adega do Bruninho")
    app.setWindowIcon(QIcon(str(LOGO_PATH)))
    if "--smoke-test" in sys.argv:
        if logo_pixmap(64,64).isNull():
            return 3
        return 0
    database: MongoDatabase | None = None
    try:
        settings = get_settings()
        configure_logging(settings)
        stylesheet = Path(__file__).parent / "resources" / "styles" / "app.qss"
        app.setStyleSheet(stylesheet.read_text(encoding="utf-8"))
        database = MongoDatabase(settings)
        database.connect()
        database.ensure_base_indexes()
        coordinator = ApplicationCoordinator(app, database)
        coordinator.start()
        app.setProperty("coordinator", coordinator)
        return app.exec()
    except SettingsError as exc:
        QMessageBox.critical(None, "Erro de configuração", str(exc))
        return 2
    except Exception:
        get_logger(__name__).exception("Não foi possível inicializar a aplicação")
        QMessageBox.critical(
            None, "Erro", "Não foi possível iniciar. Consulte o arquivo de log."
        )
        if database:
            database.close()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
