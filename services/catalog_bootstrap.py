"""Carga idempotente das categorias iniciais do varejo."""

from models.catalog import INITIAL_CATEGORIES
from repositories.catalog import CategoryRepository


def seed_categories(repository: CategoryRepository) -> None:
    for name in INITIAL_CATEGORIES: repository.upsert_initial(name)

