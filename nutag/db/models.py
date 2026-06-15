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


class Consumable(Base, TimestampMixin):
    """General consumables, for example gloves, paper, cleaning supplies."""

    __tablename__ = "consumables"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)

    unit: Mapped[Unit] = relationship()
    purchase_items: Mapped[list[PurchaseItem]] = relationship(back_populates="consumable")


class Equipment(Base, TimestampMixin):
    """Business equipment for depreciation and ROI tracking."""

    __tablename__ = "equipment"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    purchase_date: Mapped[date | None] = mapped_column(Date)
    cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)
    useful_life_months: Mapped[int | None]
    comment: Mapped[str | None] = mapped_column(Text)


class FixedExpenseCategory(Base, TimestampMixin):
    """Categories for recurring costs like rent or electricity."""

    __tablename__ = "fixed_expense_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)


class FixedExpense(Base, TimestampMixin):
    """Actual fixed cost recorded for a period."""

    __tablename__ = "fixed_expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("fixed_expense_categories.id"), nullable=False)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)

    category: Mapped[FixedExpenseCategory] = relationship()


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
    consumable_id: Mapped[int | None] = mapped_column(ForeignKey("consumables.id"))
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
    consumable: Mapped[Consumable | None] = relationship(back_populates="purchase_items")


class Preparation(Base, TimestampMixin):
    """Internal semi-finished product prepared for future production batches."""

    __tablename__ = "preparations"

    id: Mapped[int] = mapped_column(primary_key=True)
    prepared_on: Mapped[date] = mapped_column(Date, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    output_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    output_unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"), nullable=False)
    labor_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)
    other_direct_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)
    total_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)

    output_unit: Mapped[Unit] = relationship()
    ingredient_uses: Mapped[list[PreparationIngredientUse]] = relationship(
        back_populates="preparation",
        cascade="all, delete-orphan",
    )


class PreparationIngredientUse(Base, TimestampMixin):
    """Ingredient quantity and cost consumed by a preparation."""

    __tablename__ = "preparation_ingredient_uses"

    id: Mapped[int] = mapped_column(primary_key=True)
    preparation_id: Mapped[int] = mapped_column(ForeignKey("preparations.id"), nullable=False)
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id"), nullable=False)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    total_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)

    preparation: Mapped[Preparation] = relationship(back_populates="ingredient_uses")
    ingredient: Mapped[Ingredient] = relationship()
    unit: Mapped[Unit] = relationship()


class ProductionBatch(Base, TimestampMixin):
    """Final production batch with actual output and calculated cost."""

    __tablename__ = "production_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    produced_on: Mapped[date] = mapped_column(Date, nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    planned_quantity: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    actual_output_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    output_unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"), nullable=False)
    labor_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)
    equipment_depreciation: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)
    allocated_overhead: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)
    total_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="completed", nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)

    product: Mapped[Product] = relationship()
    output_unit: Mapped[Unit] = relationship()
    ingredient_uses: Mapped[list[BatchIngredientUse]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
    )
    preparation_uses: Mapped[list[BatchPreparationUse]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
    )
    packaging_uses: Mapped[list[BatchPackagingUse]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
    )
    outputs: Mapped[list[FinishedProductOutput]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
    )


class BatchIngredientUse(Base, TimestampMixin):
    """Ingredient quantity and cost consumed directly by a production batch."""

    __tablename__ = "batch_ingredient_uses"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("production_batches.id"), nullable=False)
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id"), nullable=False)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    total_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)

    batch: Mapped[ProductionBatch] = relationship(back_populates="ingredient_uses")
    ingredient: Mapped[Ingredient] = relationship()
    unit: Mapped[Unit] = relationship()


class BatchPreparationUse(Base, TimestampMixin):
    """Preparation quantity and cost consumed by a production batch."""

    __tablename__ = "batch_preparation_uses"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("production_batches.id"), nullable=False)
    preparation_id: Mapped[int] = mapped_column(ForeignKey("preparations.id"), nullable=False)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    total_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)

    batch: Mapped[ProductionBatch] = relationship(back_populates="preparation_uses")
    preparation: Mapped[Preparation] = relationship()
    unit: Mapped[Unit] = relationship()


class BatchPackagingUse(Base, TimestampMixin):
    """Packaging quantity and cost consumed by a production batch."""

    __tablename__ = "batch_packaging_uses"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("production_batches.id"), nullable=False)
    packaging_id: Mapped[int] = mapped_column(ForeignKey("packaging.id"), nullable=False)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    total_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)

    batch: Mapped[ProductionBatch] = relationship(back_populates="packaging_uses")
    packaging: Mapped[Packaging] = relationship()
    unit: Mapped[Unit] = relationship()


class FinishedProductOutput(Base, TimestampMixin):
    """Packaged finished product output from a production batch."""

    __tablename__ = "finished_product_outputs"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("production_batches.id"), nullable=False)
    package_size: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    package_unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"), nullable=False)
    package_count: Mapped[int] = mapped_column(nullable=False)
    total_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    frozen_on: Mapped[date | None] = mapped_column(Date)
    use_by: Mapped[date | None] = mapped_column(Date)
    storage_place: Mapped[str | None] = mapped_column(String(128))
    comment: Mapped[str | None] = mapped_column(Text)

    batch: Mapped[ProductionBatch] = relationship(back_populates="outputs")
    package_unit: Mapped[Unit] = relationship()


class OrderStatus(StrEnum):
    """Business status of an order."""

    NEW = "new"
    CONFIRMED = "confirmed"
    READY = "ready"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class PaymentStatus(StrEnum):
    """Payment status for accounting."""

    PENDING = "pending"
    PAID = "paid"
    ON_DELIVERY = "on_delivery"
    REFUNDED = "refunded"


class ReservationStatus(StrEnum):
    """Internal stock reservation status."""

    NOT_RESERVED = "not_reserved"
    IN_PLAN = "in_plan"
    RESERVED = "reserved"
    PARTIAL = "partial"
    RELEASED = "released"


class Order(Base, TimestampMixin):
    """Customer order for one or more products."""

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    customer_name: Mapped[str] = mapped_column(String(128), nullable=False)
    customer_contact: Mapped[str | None] = mapped_column(String(128))
    
    order_status: Mapped[OrderStatus] = mapped_column(String(32), default=OrderStatus.NEW, nullable=False)
    payment_status: Mapped[PaymentStatus] = mapped_column(String(32), default=PaymentStatus.PENDING, nullable=False)
    reservation_status: Mapped[ReservationStatus] = mapped_column(String(32), default=ReservationStatus.NOT_RESERVED, nullable=False)
    
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)
    delivery_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)
    
    comment: Mapped[str | None] = mapped_column(Text)
    has_problem: Mapped[bool] = mapped_column(default=False, nullable=False)

    items: Mapped[list[OrderItem]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
    )


class OrderItem(Base, TimestampMixin):
    """Individual product line in an order."""

    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    
    # We can link an order item to a specific batch output if it's reserved/fulfilled
    batch_output_id: Mapped[int | None] = mapped_column(ForeignKey("finished_product_outputs.id"))
    
    package_size: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    package_unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"), nullable=False)
    package_count: Mapped[int] = mapped_column(nullable=False)
    total_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    
    comment: Mapped[str | None] = mapped_column(Text)

    order: Mapped[Order] = relationship(back_populates="items")
    product: Mapped[Product] = relationship()
    package_unit: Mapped[Unit] = relationship()
    batch_output: Mapped[FinishedProductOutput | None] = relationship()
