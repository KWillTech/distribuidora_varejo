"""Persistência MongoDB de categorias e produtos."""

from __future__ import annotations

import re
from datetime import datetime, time, timezone
from decimal import Decimal
from typing import Any

from bson import ObjectId
from bson.decimal128 import Decimal128
from pymongo import ReturnDocument
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from models.auth import utc_now
from models.catalog import Category, CategoryInput, PackageType, Product, ProductInput, ProductPage
from models.packaging import PackConfiguration


class DuplicateCatalogError(RuntimeError):
    """Código, código de barras ou categoria duplicada."""


def _id(value: str) -> ObjectId | str:
    return ObjectId(value) if ObjectId.is_valid(value) else value


def _decimal(value: Any) -> Decimal | None:
    if value is None: return None
    return value.to_decimal() if isinstance(value, Decimal128) else Decimal(str(value))


class CategoryRepository:
    def __init__(self, database: Database) -> None: self._collection = database["categorias"]

    def upsert_initial(self, name: str) -> None:
        now = utc_now(); self._collection.update_one({"nome_normalizado": name.casefold()}, {"$setOnInsert": {"nome": name, "nome_normalizado": name.casefold(), "descricao": None, "ativo": True, "criado_em": now, "atualizado_em": now}}, upsert=True)

    def list_all(self, active: bool | None = None) -> list[Category]:
        query = {} if active is None else {"ativo": active}
        return [self._to_model(item) for item in self._collection.find(query).sort("nome", 1)]

    def create(self, data: CategoryInput) -> Category:
        now = utc_now(); document = {"nome": data.name, "nome_normalizado": data.name.casefold(), "descricao": data.description, "ativo": data.active, "criado_em": now, "atualizado_em": now}
        try: result = self._collection.insert_one(document)
        except DuplicateKeyError as exc: raise DuplicateCatalogError("Categoria já cadastrada.") from exc
        document["_id"] = result.inserted_id; return self._to_model(document)

    def update(self, category_id: str, data: CategoryInput) -> Category | None:
        try: document = self._collection.find_one_and_update({"_id": _id(category_id)}, {"$set": {"nome": data.name, "nome_normalizado": data.name.casefold(), "descricao": data.description, "ativo": data.active, "atualizado_em": utc_now()}}, return_document=ReturnDocument.AFTER)
        except DuplicateKeyError as exc: raise DuplicateCatalogError("Categoria já cadastrada.") from exc
        return self._to_model(document) if document else None

    @staticmethod
    def _to_model(item: dict[str, Any]) -> Category:
        return Category(id=str(item["_id"]), name=item["nome"], description=item.get("descricao"), active=item.get("ativo", True), created_at=item["criado_em"], updated_at=item["atualizado_em"])


class ProductRepository:
    def __init__(self, database: Database) -> None:
        self._collection = database["produtos"]; self._suppliers = database["fornecedores"]

    @staticmethod
    def _document(data: ProductInput) -> dict[str, Any]:
        expiry = datetime.combine(data.expiration_date, time.min, tzinfo=timezone.utc) if data.expiration_date else None
        return {
            "codigo_interno": data.internal_code, "codigo_barras_unidade": data.unit_barcode, "codigo_barras_fardo": data.pack_barcode,
            "codigos_barras": [code for code in (data.unit_barcode, data.pack_barcode) if code],
            "nome": data.name, "descricao": data.description, "categoria_id": data.category_id, "categoria_nome": data.category_name,
            "marca": data.brand, "volume": data.volume, "unidade_medida": data.measurement_unit, "tipo_embalagem": data.package_description,
            "unidades_por_fardo": data.units_per_pack, "custo_unidade": Decimal128(data.unit_cost),
            "custo_fardo": Decimal128(data.pack_cost) if data.pack_cost is not None else None,
            "preco_unidade": Decimal128(data.unit_price), "preco_fardo": Decimal128(data.pack_price) if data.pack_price is not None else None,
            "preco_promocional_unidade": Decimal128(data.promotional_unit_price) if data.promotional_unit_price is not None else None,
            "preco_promocional_fardo": Decimal128(data.promotional_pack_price) if data.promotional_pack_price is not None else None,
            "margem_lucro": Decimal128(data.unit_margin_percent), "estoque_atual_unidades": data.current_stock_units,
            "estoque_minimo": data.minimum_stock, "estoque_maximo": data.maximum_stock, "localizacao": data.storage_location,
            "fornecedor_principal_id": data.main_supplier_id, "fornecedor_principal_nome": data.main_supplier_name,
            "lote_inicial": data.initial_lot, "data_validade": expiry, "foto": data.photo_path, "ativo": data.active,
        }

    @staticmethod
    def _to_model(item: dict[str, Any]) -> Product:
        expiry = item.get("data_validade"); expiry_date = expiry.date() if isinstance(expiry, datetime) else expiry
        return Product(
            id=str(item["_id"]), internal_code=item["codigo_interno"], unit_barcode=item.get("codigo_barras_unidade"), pack_barcode=item.get("codigo_barras_fardo"),
            name=item["nome"], description=item.get("descricao"), category_id=item["categoria_id"], category_name=item["categoria_nome"],
            brand=item.get("marca"), volume=item.get("volume"), measurement_unit=item.get("unidade_medida", "UN"), package_description=item.get("tipo_embalagem"),
            units_per_pack=item.get("unidades_por_fardo"), unit_cost=_decimal(item.get("custo_unidade")) or Decimal("0"), pack_cost=_decimal(item.get("custo_fardo")),
            unit_price=_decimal(item.get("preco_unidade")) or Decimal("0"), pack_price=_decimal(item.get("preco_fardo")),
            promotional_unit_price=_decimal(item.get("preco_promocional_unidade")), promotional_pack_price=_decimal(item.get("preco_promocional_fardo")),
            current_stock_units=item.get("estoque_atual_unidades", 0), minimum_stock=item.get("estoque_minimo", 0), maximum_stock=item.get("estoque_maximo"),
            storage_location=item.get("localizacao"), main_supplier_id=item.get("fornecedor_principal_id"), main_supplier_name=item.get("fornecedor_principal_nome"),
            initial_lot=item.get("lote_inicial"), expiration_date=expiry_date, photo_path=item.get("foto"), active=item.get("ativo", True),
            created_at=item["criado_em"], updated_at=item["atualizado_em"],
        )

    def create(self, data: ProductInput) -> Product:
        now = utc_now(); document = self._document(data) | {"criado_em": now, "atualizado_em": now}
        try: result = self._collection.insert_one(document)
        except DuplicateKeyError as exc: raise DuplicateCatalogError("Código interno ou código de barras já cadastrado.") from exc
        document["_id"] = result.inserted_id; return self._to_model(document)

    def update(self, product_id: str, data: ProductInput) -> Product | None:
        try: document = self._collection.find_one_and_update({"_id": _id(product_id)}, {"$set": self._document(data) | {"atualizado_em": utc_now()}}, return_document=ReturnDocument.AFTER)
        except DuplicateKeyError as exc: raise DuplicateCatalogError("Código interno ou código de barras já cadastrado.") from exc
        return self._to_model(document) if document else None

    def get(self, product_id: str) -> Product | None:
        item = self._collection.find_one({"_id": _id(product_id)}); return self._to_model(item) if item else None

    def list_page(self, *, search: str = "", category_id: str | None = None, active: bool | None = True, low_stock: bool = False, page: int = 1, page_size: int = 20) -> ProductPage:
        query: dict[str, Any] = {}
        if active is not None: query["ativo"] = active
        if category_id: query["categoria_id"] = category_id
        if low_stock: query["$expr"] = {"$lte": ["$estoque_atual_unidades", "$estoque_minimo"]}
        if search.strip():
            safe = re.escape(search.strip()); query["$or"] = [{"nome": {"$regex": safe, "$options": "i"}}, {"codigo_interno": {"$regex": f"^{safe}", "$options": "i"}}, {"codigo_barras_unidade": search.strip()}, {"codigo_barras_fardo": search.strip()}, {"marca": {"$regex": safe, "$options": "i"}}]
        total = self._collection.count_documents(query); cursor = self._collection.find(query).sort("nome", 1).skip((page - 1) * page_size).limit(page_size)
        return ProductPage(items=[self._to_model(item) for item in cursor], total=total, page=page, page_size=page_size)

    def set_active(self, product_id: str, active: bool) -> bool:
        return self._collection.update_one({"_id": _id(product_id)}, {"$set": {"ativo": active, "atualizado_em": utc_now()}}).matched_count == 1

    def find_by_barcode(self, barcode: str) -> tuple[Product, PackageType] | None:
        item = self._collection.find_one({"codigos_barras": barcode})
        if not item: return None
        package_type = PackageType.PACK if item.get("codigo_barras_fardo") == barcode else PackageType.UNIT
        return self._to_model(item), package_type

    def update_pack_configuration(self, product_id: str, configuration: PackConfiguration) -> Product | None:
        product = self.get(product_id)
        if product is None: return None
        barcodes = [code for code in (product.unit_barcode, configuration.pack_barcode) if code]
        try:
            item = self._collection.find_one_and_update(
                {"_id": _id(product_id)},
                {"$set": {"unidades_por_fardo": configuration.units_per_pack, "codigo_barras_fardo": configuration.pack_barcode, "codigos_barras": barcodes, "preco_fardo": Decimal128(configuration.pack_price) if configuration.pack_price is not None else None, "preco_promocional_fardo": Decimal128(configuration.promotional_pack_price) if configuration.promotional_pack_price is not None else None, "atualizado_em": utc_now()}},
                return_document=ReturnDocument.AFTER,
            )
        except DuplicateKeyError as exc: raise DuplicateCatalogError("Código de barras já cadastrado em outro produto.") from exc
        return self._to_model(item) if item else None

    def sync_category_name(self, category_id: str, category_name: str) -> None:
        self._collection.update_many({"categoria_id": category_id}, {"$set": {"categoria_nome": category_name, "atualizado_em": utc_now()}})

    def supplier_options(self) -> list[tuple[str, str]]:
        return [(str(item["_id"]), item.get("nome_fantasia") or item["razao_social"]) for item in self._suppliers.find({"ativo": True}, {"razao_social": 1, "nome_fantasia": 1}).sort("razao_social", 1)]

    def active_products(self) -> list[Product]:
        return [self._to_model(item) for item in self._collection.find({"ativo": True}).sort("nome", 1)]

    def update_unit_cost(self, product_id: str, unit_cost: Decimal) -> None:
        self._collection.update_one({"_id": _id(product_id)}, {"$set": {"custo_unidade": Decimal128(unit_cost), "atualizado_em": utc_now()}})
