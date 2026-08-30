"""Conversão e validação de unidade/fardo, independente do futuro PDV."""

from __future__ import annotations

from decimal import Decimal

from models.auth import AuthenticatedSession, Permission
from models.catalog import PackageType, Product
from models.packaging import PackConfiguration, SalePackageQuote, SalePackageRequest
from repositories.auth import AuditRepository
from repositories.catalog import ProductRepository
from services.rbac import require_permission


class InsufficientStockError(ValueError):
    """Saldo em unidades não cobre a embalagem solicitada."""


class PackagingService:
    def __init__(self, products: ProductRepository, audit: AuditRepository) -> None:
        self._products = products; self._audit = audit

    def find_by_barcode(self, session: AuthenticatedSession, barcode: str) -> tuple[Product, PackageType]:
        require_permission(session, Permission.PRODUCTS_VIEW)
        result = self._products.find_by_barcode(barcode)
        if result is None: raise ValueError("Código de barras não encontrado.")
        return result

    def quote(self, session: AuthenticatedSession, request: SalePackageRequest) -> SalePackageQuote:
        require_permission(session, Permission.PRODUCTS_VIEW)
        product = request.product
        if not product.active: raise ValueError("Produto inativo não pode ser vendido.")
        if request.package_type == PackageType.PACK:
            if not product.units_per_pack or product.pack_price is None:
                raise ValueError("Produto não configurado para venda por fardo.")
            converted = request.quantity * product.units_per_pack
            price = product.promotional_pack_price if request.use_promotional_price and product.promotional_pack_price is not None else product.pack_price
        else:
            converted = request.quantity
            price = product.promotional_unit_price if request.use_promotional_price and product.promotional_unit_price is not None else product.unit_price
        if converted > product.current_stock_units:
            raise InsufficientStockError(f"Estoque insuficiente: disponível {product.current_stock_units} unidade(s), necessário {converted}.")
        return SalePackageQuote(
            product_id=product.id or "", product_name=product.name, package_type=request.package_type,
            informed_quantity=request.quantity, converted_units=converted, unit_package_price=price,
            total=(price * request.quantity).quantize(Decimal("0.01")), stock_before_units=product.current_stock_units,
            stock_after_units=product.current_stock_units - converted,
        )

    def quote_cart(self, session: AuthenticatedSession, requests: list[SalePackageRequest]) -> list[SalePackageQuote]:
        """Valida linhas mistas considerando o saldo acumulado por produto."""
        remaining: dict[str, int] = {}
        quotes: list[SalePackageQuote] = []
        for request in requests:
            key = request.product.id or request.product.internal_code
            available = remaining.get(key, request.product.current_stock_units)
            current_request = request.model_copy(
                update={"product": request.product.model_copy(update={"current_stock_units": available})}
            )
            quote = self.quote(session, current_request)
            remaining[key] = quote.stock_after_units
            quotes.append(quote)
        return quotes

    @staticmethod
    def returned_units(product: Product, package_type: PackageType, quantity: int) -> int:
        if quantity <= 0: raise ValueError("Quantidade da devolução deve ser positiva.")
        if package_type == PackageType.PACK:
            if not product.units_per_pack: raise ValueError("Produto não possui composição de fardo.")
            return quantity * product.units_per_pack
        return quantity

    def configure_pack(self, session: AuthenticatedSession, product_id: str, configuration: PackConfiguration) -> Product:
        require_permission(session, Permission.PRODUCTS_EDIT); require_permission(session, Permission.PRODUCTS_CHANGE_PRICE)
        previous = self._products.get(product_id)
        if previous is None: raise ValueError("Produto não encontrado.")
        if configuration.pack_barcode and configuration.pack_barcode == previous.unit_barcode:
            raise ValueError("Código do fardo deve ser diferente do código da unidade.")
        updated = self._products.update_pack_configuration(product_id, configuration)
        if updated is None: raise ValueError("Produto não encontrado.")
        self._audit.record(user=session.user, action="composicao_fardo_alterada", module="produtos", affected_id=product_id, details={"antes": {"unidades": previous.units_per_pack, "codigo": previous.pack_barcode, "preco": str(previous.pack_price)}, "depois": {"unidades": configuration.units_per_pack, "codigo": configuration.pack_barcode, "preco": str(configuration.pack_price)}})
        if previous.pack_price != configuration.pack_price or previous.promotional_pack_price != configuration.promotional_pack_price:
            self._audit.record(user=session.user, action="precos_alterados", module="produtos", affected_id=product_id, details={"tipo": "fardo", "antes": [str(previous.pack_price), str(previous.promotional_pack_price)], "depois": [str(configuration.pack_price), str(configuration.promotional_pack_price)]})
        return updated
