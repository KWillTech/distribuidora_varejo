"""Regras e autorização do catálogo de categorias e produtos."""

from models.auth import AuthenticatedSession, Permission
from models.catalog import Category, CategoryInput, Product, ProductInput, ProductPage
from repositories.auth import AuditRepository
from repositories.catalog import CategoryRepository, ProductRepository
from services.rbac import require_permission


class CatalogService:
    def __init__(self, categories: CategoryRepository, products: ProductRepository, audit: AuditRepository) -> None:
        self._categories = categories; self._products = products; self._audit = audit

    def list_categories(self, session: AuthenticatedSession, active: bool | None = True) -> list[Category]:
        require_permission(session, Permission.PRODUCTS_VIEW); return self._categories.list_all(active)

    def create_category(self, session: AuthenticatedSession, data: CategoryInput) -> Category:
        require_permission(session, Permission.CATEGORIES_MANAGE); result = self._categories.create(data); self._audit.record(user=session.user, action="categoria_criada", module="categorias", affected_id=result.id); return result

    def update_category(self, session: AuthenticatedSession, category_id: str, data: CategoryInput) -> Category:
        require_permission(session, Permission.CATEGORIES_MANAGE); result = self._categories.update(category_id, data)
        if result is None: raise ValueError("Categoria não encontrada.")
        self._products.sync_category_name(category_id, result.name)
        self._audit.record(user=session.user, action="categoria_alterada", module="categorias", affected_id=category_id); return result

    def list_products(self, session: AuthenticatedSession, **filters) -> ProductPage:
        require_permission(session, Permission.PRODUCTS_VIEW); page = filters.get("page", 1); size = filters.get("page_size", 20)
        if page < 1 or size not in (10, 20, 50, 100): raise ValueError("Paginação inválida.")
        return self._products.list_page(**filters)

    def get_product(self, session: AuthenticatedSession, product_id: str) -> Product:
        require_permission(session, Permission.PRODUCTS_VIEW); result = self._products.get(product_id)
        if result is None: raise ValueError("Produto não encontrado.")
        return result

    def create_product(self, session: AuthenticatedSession, data: ProductInput) -> Product:
        require_permission(session, Permission.PRODUCTS_CREATE); result = self._products.create(data); self._audit.record(user=session.user, action="produto_criado", module="produtos", affected_id=result.id); return result

    def update_product(self, session: AuthenticatedSession, product_id: str, data: ProductInput) -> Product:
        require_permission(session, Permission.PRODUCTS_EDIT); previous = self.get_product(session, product_id)
        price_changed = (previous.unit_price, previous.pack_price, previous.promotional_unit_price, previous.promotional_pack_price) != (data.unit_price, data.pack_price, data.promotional_unit_price, data.promotional_pack_price)
        pack_changed = previous.units_per_pack != data.units_per_pack
        stock_changed = previous.current_stock_units != data.current_stock_units
        if price_changed: require_permission(session, Permission.PRODUCTS_CHANGE_PRICE)
        if stock_changed: require_permission(session, Permission.STOCK_ADJUST)
        result = self._products.update(product_id, data)
        if result is None: raise ValueError("Produto não encontrado.")
        self._audit.record(user=session.user, action="produto_alterado", module="produtos", affected_id=product_id)
        if price_changed: self._audit.record(user=session.user, action="precos_alterados", module="produtos", affected_id=product_id, details={"antes": [str(previous.unit_price), str(previous.pack_price)], "depois": [str(data.unit_price), str(data.pack_price)]})
        if pack_changed: self._audit.record(user=session.user, action="composicao_fardo_alterada", module="produtos", affected_id=product_id, details={"antes": previous.units_per_pack, "depois": data.units_per_pack})
        if stock_changed: self._audit.record(user=session.user, action="estoque_produto_alterado", module="produtos", affected_id=product_id, details={"saldo_anterior": previous.current_stock_units, "saldo_final": data.current_stock_units, "origem": "cadastro_produto"})
        return result

    def set_product_active(self, session: AuthenticatedSession, product_id: str, active: bool, reason: str) -> None:
        require_permission(session, Permission.PRODUCTS_DEACTIVATE)
        if not reason.strip(): raise ValueError("Informe o motivo da alteração.")
        if not self._products.set_active(product_id, active): raise ValueError("Produto não encontrado.")
        self._audit.record(user=session.user, action="produto_ativado" if active else "produto_inativado", module="produtos", affected_id=product_id, reason=reason)

    def supplier_options(self, session: AuthenticatedSession) -> list[tuple[str, str]]:
        require_permission(session, Permission.PRODUCTS_VIEW); return self._products.supplier_options()

    def active_products(self, session: AuthenticatedSession) -> list[Product]:
        require_permission(session, Permission.STOCK_VIEW); return self._products.active_products()

    def pos_products(self, session: AuthenticatedSession) -> list[Product]:
        require_permission(session, Permission.POS_ACCESS); return self._products.active_products()
