"""Testes da tabela e visibilidade do catálogo."""

from decimal import Decimal

from models.auth import AuthenticatedSession, Permission, ProfileCode, User
from models.catalog import Category, Product, ProductPage
from views.catalog_view import CatalogView


class FakeCatalogService:
    def list_categories(self, session, active=True): return [Category(id="c1", name="Cervejas")]
    def list_products(self, session, **kwargs):
        product = Product(id="p1", internal_code="CER-001", name="Cerveja", category_id="c1", category_name="Cervejas", main_supplier_id="f1", main_supplier_name="Distribuidora Teste", unit_cost=Decimal("3.00"), unit_price=Decimal("5.00"))
        return ProductPage(items=[product], total=1, page=1, page_size=kwargs["page_size"])


class FakePackagingService: pass


def test_supplier_column_and_information_button(qtbot) -> None:
    user = User(id="u1", username="caixa", email="caixa@example.com", full_name="Pessoa Caixa", profile_code=ProfileCode.CASHIER)
    session = AuthenticatedSession(session_id="s1", user=user, permissions={Permission.PRODUCTS_VIEW})
    view = CatalogView(session, FakeCatalogService(), FakePackagingService()); qtbot.addWidget(view)
    assert view.product_table.horizontalHeaderItem(3).text() == "Fornecedor"
    assert view.product_table.item(0, 3).text() == "Distribuidora Teste"
    assert view.product_table.horizontalHeaderItem(6).text() == "Estoque mínimo"
    assert view.product_table.isColumnHidden(7) is True
    buttons = [button.text() for button in view.findChildren(type(view.next))]
    assert "Exibir informações" in buttons
