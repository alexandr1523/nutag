"""Service functions for reference/dictionary records."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from nutag.db.models import Ingredient, Packaging, PreparationType, Product, Unit


def create_unit(session: Session, *, name: str, short_name: str, comment: str | None = None) -> Unit:
    """Create a measurement unit."""

    unit = Unit(name=name, short_name=short_name, comment=comment)
    session.add(unit)
    session.flush()
    return unit


def create_product(session: Session, *, name: str, comment: str | None = None) -> Product:
    """Create a sellable product."""

    product = Product(name=name, comment=comment)
    session.add(product)
    session.flush()
    return product


def create_preparation_type(session: Session, *, name: str, comment: str | None = None) -> PreparationType:
    """Create a preparation type for internal semi-finished products."""

    preparation_type = PreparationType(name=name, comment=comment)
    session.add(preparation_type)
    session.flush()
    return preparation_type


def create_ingredient(
    session: Session,
    *,
    name: str,
    unit: Unit,
    comment: str | None = None,
) -> Ingredient:
    """Create an ingredient linked to its base measurement unit."""

    ingredient = Ingredient(name=name, unit=unit, comment=comment)
    session.add(ingredient)
    session.flush()
    return ingredient


def create_packaging(
    session: Session,
    *,
    name: str,
    unit: Unit,
    comment: str | None = None,
) -> Packaging:
    """Create a packaging inventory item linked to its base unit."""

    packaging = Packaging(name=name, unit=unit, comment=comment)
    session.add(packaging)
    session.flush()
    return packaging


def list_units(session: Session) -> list[Unit]:
    """Return units ordered by name."""

    return list(session.scalars(select(Unit).order_by(Unit.name)))


def list_products(session: Session) -> list[Product]:
    """Return products ordered by name."""

    return list(session.scalars(select(Product).order_by(Product.name)))


def list_preparation_types(session: Session) -> list[PreparationType]:
    """Return preparation types ordered by name."""

    return list(session.scalars(select(PreparationType).order_by(PreparationType.name)))


def list_ingredients(session: Session) -> list[Ingredient]:
    """Return ingredients ordered by name."""

    return list(session.scalars(select(Ingredient).order_by(Ingredient.name)))


def list_packaging(session: Session) -> list[Packaging]:
    """Return packaging items ordered by name."""

    return list(session.scalars(select(Packaging).order_by(Packaging.name)))
