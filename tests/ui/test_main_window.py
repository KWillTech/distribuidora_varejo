"""Teste da navegação e carregamento assíncrono da janela principal."""

from PySide6.QtCore import Qt

from models.auth import AuthenticatedSession, Permission, ProfileCode, User
from models.dashboard import DashboardData
from views.main_window import MainWindow


class FakeDashboardService:
    def load(self, session, filters):
        return DashboardData(sales_today=7)


class FakeUserService:
    def list_users(self, session):
        return [session.user]


class FakeCustomerService:
    def list_page(self, session, **kwargs):
        from models.customer import CustomerPage
        return CustomerPage(items=[], total=0, page=1, page_size=kwargs.get("page_size", 20))


class FakeSupplierService:
    def list_page(self, session, **kwargs):
        from models.supplier import SupplierPage
        return SupplierPage(items=[], total=0, page=1, page_size=kwargs.get("page_size", 20))


class FakeCatalogService:
    pass


class FakePackagingService:
    pass


class FakeStockService:
    pass


class FakePurchaseService:
    pass


def test_sidebar_collapses_and_dashboard_loads(qtbot) -> None:
    user = User(id="u1", username="admin", email="admin@example.com", full_name="Administrador Principal", profile_code=ProfileCode.ADMIN, must_change_password=False)
    session = AuthenticatedSession(session_id="s1", user=user, permissions={Permission.DASHBOARD_VIEW, Permission.USERS_VIEW})
    window = MainWindow(session, FakeDashboardService(), FakeUserService(), FakeCustomerService(), FakeSupplierService(), FakeCatalogService(), FakePackagingService(), FakeStockService(), FakePurchaseService())
    qtbot.addWidget(window)
    window.show()
    dashboard = window.pages.widget(0)
    qtbot.waitUntil(lambda: dashboard.cards["sales_today"].value_label.text() == "7", timeout=3000)
    assert window.sidebar.width() == 230
    assert window.dashboard_button.isChecked()
    assert [label.text() for label in window.section_labels] == ["GERAL", "ATENDIMENTO", "GESTÃO", "CADASTROS", "SISTEMA"]
    qtbot.mouseClick(window.collapse_button, Qt.MouseButton.LeftButton)
    assert window.sidebar.width() == 68
    assert window.dashboard_button.property("expandedText") == "📊  Painel"
    assert window.users_button.property("expandedText") == "👥  Usuários"
    assert all(label.isHidden() for label in window.section_labels)
    assert window.customers_button.property("expandedText") == "👤  Clientes"
    assert window.suppliers_button.property("expandedText") == "🏭  Fornecedores"
    assert window.catalog_button.property("expandedText") == "🍺  Produtos"
    assert window.stock_button.property("expandedText") == "📦  Estoque"
    assert window.purchases_button.property("expandedText") == "🧾  Compras"
