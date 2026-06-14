"""Initial SQLAlchemy models for the Nutag MVP.

The first database slice focuses on dictionaries and purchases because they are
needed before inventory balances, preparations, batches and orders can be built
on top of persistent data.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nutag.db.base import Base


class PurchaseItemType(StrEnum):
    """Supported purchase item categories for the first inventory slice."""

    INGREDIENT = "ingredient"
    PACKAGING = "packaging"
    CONSUMABLE = "consumable"


class TimestampMixin:
    """Created/updated timestamps for mutable business records."""

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Unit(Base, TimestampMixin):
    """Measurement unit, for example kg, g, piece or package."""

    __tablename__ = "units"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    short_name: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)

    ingredients: Mapped[list[Ingredient]] = relationship(back_populates="unit")
    packaging_items: Mapped[list[Packaging]] = relationship(back_populates="unit")
    purchase_items: Mapped[list[PurchaseItem]] = relationship(back_populates="unit")


class Product(Base, TimestampMixin):
    """Sellable product, for example pelmeni, buuzy or vareniki."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)


class Ingredient(Base, TimestampMixin):
    """Raw ingredient used in preparations and production batches."""

    __tablename__ = "ingredients"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)

    unit: Mapped[Unit] = relationship(back_populates="ingredients")
    purchase_items: Mapped[list[PurchaseItem]] = relationship(back_populates="ingredient")


class Packaging(Base, TimestampMixin):
    """Packaging item tracked as inventory, for example 0.5 kg or 1 kg containers."""

    __tablename__ = "packaging"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)

    unit: Mapped[Unit] = relationship(back_populates="packaging_items")
    purchase_items: Mapped[list[PurchaseItem]] = relationship(back_populates="packaging")


class Purchase(Base, TimestampMixin):
    """Purchase document containing one or more purchased positions."""

    __tablename__ = "purchases"

    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_date: Mapped[date] = mapped_column(Date, nullable=False)
    supplier: Mapped[str | None] = mapped_column(String(128))
    purchased_by: Mapped[str | None] = mapped_column(String(128))
    shopping_minutes: Mapped[int | None]
    transport_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)

    items: Mapped[list[PurchaseItem]] = relationship(
        back_populates="purchase",
        cascade="all, delete-orphan",
    )


class PurchaseItem(Base, TimestampMixin):
    """Single line inside a purchase document."""

    __tablename__ = "purchase_items"
    __table_args__ = (
        UniqueConstraint("purchase_id", "line_number", name="uq_purchase_items_purchase_line"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.id"), nullable=False)
    line_number: Mapped[int] = mapped_column(nullable=False)
    item_type: Mapped[PurchaseItemType] = mapped_column(String(32), nullable=False)
    ingredient_id: Mapped[int | None] = mapped_column(ForeignKey("ingredients.id"))
    packaging_id: Mapped[int | None] = mapped_column(ForeignKey("packaging.id"))
    item_name: Mapped[str] = mapped_column(String(128), nullable=False)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    expires_on: Mapped[date | None] = mapped_column(Date)
    comment: Mapped[str | None] = mapped_column(Text)

    purchase: Mapped[Purchase] = relationship(back_populates="items")
    unit: Mapped[Unit] = relationship(back_populates="purchase_items")
    ingredient: Mapped[Ingredient | None] = relationship(back_populates="purchase_items")
    packaging: Mapped[Packaging | None] = relationship(back_populates="purchase_items")
