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

    INGREDIENT = "Ингредиент"
    PACKAGING = "Упаковка"
    CONSUMABLE = "Расходник"


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


class PreparationType(Base, TimestampMixin):
    """Reference type for internal preparations/semi-finished products."""

    __tablename__ = "preparation_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)

    preparations: Mapped[list[Preparation]] = relationship(back_populates="preparation_type")


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
    hourly_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)
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


class LaborRate(Base, TimestampMixin):
    """Hourly labor rate for cost calculations."""

    __tablename__ = "labor_rates"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), default="Default", nullable=False)
    hourly_rate: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)


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
    preparation_type_id: Mapped[int | None] = mapped_column(ForeignKey("preparation_types.id"))
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    output_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    waste_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal("0"), nullable=False)
    output_unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"), nullable=False)
    labor_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)
    other_direct_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)
    total_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)

    preparation_type: Mapped[PreparationType | None] = relationship(back_populates="preparations")
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
    purchase_item_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_items.id"))
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    waste_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal("0"), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    total_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)

    preparation: Mapped[Preparation] = relationship(back_populates="ingredient_uses")
    ingredient: Mapped[Ingredient] = relationship()
    purchase_item: Mapped[PurchaseItem | None] = relationship()
    unit: Mapped[Unit] = relationship()


class ProductionBatch(Base, TimestampMixin):
    """Final production batch with actual output and calculated cost."""

    __tablename__ = "production_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    produced_on: Mapped[date] = mapped_column(Date, nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    planned_quantity: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    actual_output_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    waste_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal("0"), nullable=False)
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
    bulk_outputs: Mapped[list[FinishedProductBulkOutput]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
    )


class BatchIngredientUse(Base, TimestampMixin):
    """Ingredient quantity and cost consumed directly by a production batch."""

    __tablename__ = "batch_ingredient_uses"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("production_batches.id"), nullable=False)
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id"), nullable=False)
    purchase_item_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_items.id"))
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    total_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)

    batch: Mapped[ProductionBatch] = relationship(back_populates="ingredient_uses")
    ingredient: Mapped[Ingredient] = relationship()
    purchase_item: Mapped[PurchaseItem | None] = relationship()
    unit: Mapped[Unit] = relationship()


class BatchPreparationUse(Base, TimestampMixin):
    """Preparation quantity and cost consumed by a production batch."""

    __tablename__ = "batch_preparation_uses"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("production_batches.id"), nullable=False)
    preparation_id: Mapped[int] = mapped_column(ForeignKey("preparations.id"), nullable=False)
    source_preparation_id: Mapped[int | None] = mapped_column(ForeignKey("preparations.id"))
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    total_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)

    batch: Mapped[ProductionBatch] = relationship(back_populates="preparation_uses")
    preparation: Mapped[Preparation] = relationship(foreign_keys=[preparation_id])
    source_preparation: Mapped[Preparation | None] = relationship(foreign_keys=[source_preparation_id])
    unit: Mapped[Unit] = relationship()


class BatchPackagingUse(Base, TimestampMixin):
    """Packaging quantity and cost consumed by a production batch."""

    __tablename__ = "batch_packaging_uses"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("production_batches.id"), nullable=False)
    packaging_id: Mapped[int] = mapped_column(ForeignKey("packaging.id"), nullable=False)
    purchase_item_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_items.id"))
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    total_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)

    batch: Mapped[ProductionBatch] = relationship(back_populates="packaging_uses")
    packaging: Mapped[Packaging] = relationship()
    purchase_item: Mapped[PurchaseItem | None] = relationship()
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
    packing_operation: Mapped[FinishedProductPacking | None] = relationship(
        back_populates="finished_output",
        uselist=False,
    )


class FinishedProductBulkOutput(Base, TimestampMixin):
    """Unpacked finished product stock from a production batch."""

    __tablename__ = "finished_product_bulk_outputs"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("production_batches.id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"), nullable=False)
    frozen_on: Mapped[date | None] = mapped_column(Date)
    use_by: Mapped[date | None] = mapped_column(Date)
    storage_place: Mapped[str | None] = mapped_column(String(128))
    comment: Mapped[str | None] = mapped_column(Text)

    batch: Mapped[ProductionBatch] = relationship(back_populates="bulk_outputs")
    unit: Mapped[Unit] = relationship()
    packings: Mapped[list[FinishedProductPacking]] = relationship(
        back_populates="source_bulk_output",
        cascade="all, delete-orphan",
    )


class FinishedProductPacking(Base, TimestampMixin):
    """Packing operation that converts unpacked finished product into packaged stock."""

    __tablename__ = "finished_product_packings"

    id: Mapped[int] = mapped_column(primary_key=True)
    packed_on: Mapped[date] = mapped_column(Date, nullable=False)
    source_bulk_output_id: Mapped[int] = mapped_column(ForeignKey("finished_product_bulk_outputs.id"), nullable=False)
    finished_output_id: Mapped[int] = mapped_column(ForeignKey("finished_product_outputs.id"), nullable=False)
    packaging_id: Mapped[int] = mapped_column(ForeignKey("packaging.id"), nullable=False)
    packaging_purchase_item_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_items.id"))
    packaging_unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"), nullable=False)
    packaging_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    packaging_unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    packaging_total_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)

    source_bulk_output: Mapped[FinishedProductBulkOutput] = relationship(back_populates="packings")
    finished_output: Mapped[FinishedProductOutput] = relationship(back_populates="packing_operation")
    packaging: Mapped[Packaging] = relationship()
    packaging_purchase_item: Mapped[PurchaseItem | None] = relationship()
    packaging_unit: Mapped[Unit] = relationship()


class OrderStatus(StrEnum):
    """Business status of an order."""

    NEW = "Новый"
    CONFIRMED = "Подтвержден"
    READY = "Готов"
    DELIVERED = "Выдан"
    CANCELLED = "Отменен"


class PaymentStatus(StrEnum):
    """Payment status for accounting."""

    PENDING = "Ожидает"
    PAID = "Оплачен"
    ON_DELIVERY = "При получении"
    REFUNDED = "Возврат"


class ReservationStatus(StrEnum):
    """Internal stock reservation status."""

    NOT_RESERVED = "Не зарезервирован"
    IN_PLAN = "В плане"
    RESERVED = "Зарезервирован"
    PARTIAL = "Частично"
    RELEASED = "Снят"


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
