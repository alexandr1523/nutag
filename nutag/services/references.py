"""Service functions for reference/dictionary records."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from nutag.db.models import (
    BatchIngredientUse,
    BatchPackagingUse,
    BatchPreparationUse,
    Consumable,
    FinishedProductBulkOutput,
    FinishedProductPacking,
    FinishedProductOutput,
    Ingredient,
    OrderItem,
    Packaging,
    Preparation,
    PreparationIngredientUse,
    PreparationType,
    ProductionBatch,
    Product,
    PurchaseItem,
    Unit,
)


def _clean_required_text(value: str | None, field_name: str) -> str:
    cleaned = " ".join((value or "").strip().split())
    if not cleaned:
        raise ValueError(f"{field_name} обязательно")
    return cleaned


def _clean_optional_text(value: str | None) -> str | None:
    cleaned = " ".join((value or "").strip().split())
    return cleaned or None


def _same_text(left: str, right: str) -> bool:
    return left.strip().casefold() == right.strip().casefold()


def _get_required(session: Session, model: type, record_id: int):
    record = session.get(model, record_id)
    if record is None:
        raise ValueError("Запись справочника не найдена")
    return record


def _ensure_unique_text(
    session: Session,
    model: type,
    field_name: str,
    cleaned_value: str,
    message: str,
    *,
    current_id: int | None = None,
) -> None:
    existing_records = session.scalars(select(model)).all()
    for record in existing_records:
        if current_id is not None and record.id == current_id:
            continue
        if _same_text(getattr(record, field_name), cleaned_value):
            raise ValueError(message)


def _record_exists(session: Session, statement) -> bool:
    return session.scalar(statement.limit(1)) is not None


def _ingredient_has_usage(session: Session, ingredient_id: int) -> bool:
    return any(
        (
            _record_exists(session, select(PurchaseItem.id).where(PurchaseItem.ingredient_id == ingredient_id)),
            _record_exists(
                session,
                select(PreparationIngredientUse.id).where(PreparationIngredientUse.ingredient_id == ingredient_id),
            ),
            _record_exists(session, select(BatchIngredientUse.id).where(BatchIngredientUse.ingredient_id == ingredient_id)),
        )
    )


def _packaging_has_usage(session: Session, packaging_id: int) -> bool:
    return any(
        (
            _record_exists(session, select(PurchaseItem.id).where(PurchaseItem.packaging_id == packaging_id)),
            _record_exists(session, select(BatchPackagingUse.id).where(BatchPackagingUse.packaging_id == packaging_id)),
            _record_exists(
                session,
                select(FinishedProductPacking.id).where(FinishedProductPacking.packaging_id == packaging_id),
            ),
        )
    )


def _consumable_has_usage(session: Session, consumable_id: int) -> bool:
    return _record_exists(session, select(PurchaseItem.id).where(PurchaseItem.consumable_id == consumable_id))


def _unit_has_usage(session: Session, unit_id: int) -> bool:
    return any(
        (
            _record_exists(session, select(Ingredient.id).where(Ingredient.unit_id == unit_id)),
            _record_exists(session, select(Packaging.id).where(Packaging.unit_id == unit_id)),
            _record_exists(session, select(Consumable.id).where(Consumable.unit_id == unit_id)),
            _record_exists(session, select(PurchaseItem.id).where(PurchaseItem.unit_id == unit_id)),
            _record_exists(session, select(Preparation.id).where(Preparation.output_unit_id == unit_id)),
            _record_exists(
                session,
                select(PreparationIngredientUse.id).where(PreparationIngredientUse.unit_id == unit_id),
            ),
            _record_exists(session, select(ProductionBatch.id).where(ProductionBatch.output_unit_id == unit_id)),
            _record_exists(session, select(BatchIngredientUse.id).where(BatchIngredientUse.unit_id == unit_id)),
            _record_exists(session, select(BatchPreparationUse.id).where(BatchPreparationUse.unit_id == unit_id)),
            _record_exists(session, select(BatchPackagingUse.id).where(BatchPackagingUse.unit_id == unit_id)),
            _record_exists(
                session,
                select(FinishedProductOutput.id).where(FinishedProductOutput.package_unit_id == unit_id),
            ),
            _record_exists(
                session,
                select(FinishedProductBulkOutput.id).where(FinishedProductBulkOutput.unit_id == unit_id),
            ),
            _record_exists(
                session,
                select(FinishedProductPacking.id).where(FinishedProductPacking.packaging_unit_id == unit_id),
            ),
            _record_exists(session, select(OrderItem.id).where(OrderItem.package_unit_id == unit_id)),
        )
    )


def _product_has_usage(session: Session, product_id: int) -> bool:
    return any(
        (
            _record_exists(session, select(ProductionBatch.id).where(ProductionBatch.product_id == product_id)),
            _record_exists(session, select(OrderItem.id).where(OrderItem.product_id == product_id)),
        )
    )


def _preparation_type_has_usage(session: Session, preparation_type_id: int) -> bool:
    return _record_exists(session, select(Preparation.id).where(Preparation.preparation_type_id == preparation_type_id))


def create_unit(session: Session, *, name: str, short_name: str, comment: str | None = None) -> Unit:
    """Create a measurement unit."""

    cleaned_name = _clean_required_text(name, "Название")
    cleaned_short_name = _clean_required_text(short_name, "Сокращение")

    _ensure_unique_text(session, Unit, "name", cleaned_name, "Единица измерения с таким названием уже существует")
    _ensure_unique_text(
        session,
        Unit,
        "short_name",
        cleaned_short_name,
        "Единица измерения с таким сокращением уже существует",
    )

    unit = Unit(name=cleaned_name, short_name=cleaned_short_name, comment=_clean_optional_text(comment))
    session.add(unit)
    session.flush()
    return unit


def create_product(session: Session, *, name: str, comment: str | None = None) -> Product:
    """Create a sellable product."""

    cleaned_name = _clean_required_text(name, "Название")
    _ensure_unique_text(session, Product, "name", cleaned_name, "Продукт с таким названием уже существует")

    product = Product(name=cleaned_name, comment=_clean_optional_text(comment))
    session.add(product)
    session.flush()
    return product


def create_preparation_type(session: Session, *, name: str, comment: str | None = None) -> PreparationType:
    """Create a preparation type for internal semi-finished products."""

    cleaned_name = _clean_required_text(name, "Название")
    _ensure_unique_text(
        session,
        PreparationType,
        "name",
        cleaned_name,
        "Вид заготовки с таким названием уже существует",
    )

    preparation_type = PreparationType(name=cleaned_name, comment=_clean_optional_text(comment))
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

    cleaned_name = _clean_required_text(name, "Название")

    _ensure_unique_text(session, Ingredient, "name", cleaned_name, "Ингредиент с таким названием уже существует")

    ingredient = Ingredient(name=cleaned_name, unit=unit, comment=_clean_optional_text(comment))
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

    cleaned_name = _clean_required_text(name, "Название")
    _ensure_unique_text(session, Packaging, "name", cleaned_name, "Упаковка с таким названием уже существует")

    packaging = Packaging(name=cleaned_name, unit=unit, comment=_clean_optional_text(comment))
    session.add(packaging)
    session.flush()
    return packaging


def create_consumable(
    session: Session,
    *,
    name: str,
    unit: Unit,
    comment: str | None = None,
) -> Consumable:
    """Create a consumable inventory item linked to its base unit."""

    cleaned_name = _clean_required_text(name, "Название")
    _ensure_unique_text(session, Consumable, "name", cleaned_name, "Расходник с таким названием уже существует")

    consumable = Consumable(name=cleaned_name, unit=unit, comment=_clean_optional_text(comment))
    session.add(consumable)
    session.flush()
    return consumable


def update_unit(
    session: Session,
    unit_id: int,
    *,
    name: str,
    short_name: str,
    comment: str | None = None,
) -> Unit:
    """Update a measurement unit while preserving its ID."""

    unit = _get_required(session, Unit, unit_id)
    cleaned_name = _clean_required_text(name, "Название")
    cleaned_short_name = _clean_required_text(short_name, "Сокращение")
    _ensure_unique_text(
        session,
        Unit,
        "name",
        cleaned_name,
        "Единица измерения с таким названием уже существует",
        current_id=unit.id,
    )
    _ensure_unique_text(
        session,
        Unit,
        "short_name",
        cleaned_short_name,
        "Единица измерения с таким сокращением уже существует",
        current_id=unit.id,
    )

    unit.name = cleaned_name
    unit.short_name = cleaned_short_name
    unit.comment = _clean_optional_text(comment)
    session.flush()
    return unit


def update_product(session: Session, product_id: int, *, name: str, comment: str | None = None) -> Product:
    """Update a product while preserving its ID."""

    product = _get_required(session, Product, product_id)
    cleaned_name = _clean_required_text(name, "Название")
    _ensure_unique_text(
        session,
        Product,
        "name",
        cleaned_name,
        "Продукт с таким названием уже существует",
        current_id=product.id,
    )

    product.name = cleaned_name
    product.comment = _clean_optional_text(comment)
    session.flush()
    return product


def update_preparation_type(
    session: Session,
    preparation_type_id: int,
    *,
    name: str,
    comment: str | None = None,
) -> PreparationType:
    """Update a preparation type while preserving its ID."""

    preparation_type = _get_required(session, PreparationType, preparation_type_id)
    cleaned_name = _clean_required_text(name, "Название")
    _ensure_unique_text(
        session,
        PreparationType,
        "name",
        cleaned_name,
        "Вид заготовки с таким названием уже существует",
        current_id=preparation_type.id,
    )

    preparation_type.name = cleaned_name
    preparation_type.comment = _clean_optional_text(comment)
    session.flush()
    return preparation_type


def update_ingredient(
    session: Session,
    ingredient_id: int,
    *,
    name: str,
    unit: Unit,
    comment: str | None = None,
) -> Ingredient:
    """Update an ingredient, blocking unit changes after operational usage."""

    ingredient = _get_required(session, Ingredient, ingredient_id)
    cleaned_name = _clean_required_text(name, "Название")
    _ensure_unique_text(
        session,
        Ingredient,
        "name",
        cleaned_name,
        "Ингредиент с таким названием уже существует",
        current_id=ingredient.id,
    )

    if ingredient.unit_id != unit.id and _ingredient_has_usage(session, ingredient.id):
        raise ValueError("Единицу измерения нельзя изменить: ингредиент уже использовался в операциях")

    ingredient.name = cleaned_name
    ingredient.unit = unit
    ingredient.comment = _clean_optional_text(comment)
    session.flush()
    return ingredient


def update_packaging(
    session: Session,
    packaging_id: int,
    *,
    name: str,
    unit: Unit,
    comment: str | None = None,
) -> Packaging:
    """Update packaging, blocking unit changes after operational usage."""

    packaging = _get_required(session, Packaging, packaging_id)
    cleaned_name = _clean_required_text(name, "Название")
    _ensure_unique_text(
        session,
        Packaging,
        "name",
        cleaned_name,
        "Упаковка с таким названием уже существует",
        current_id=packaging.id,
    )

    if packaging.unit_id != unit.id and _packaging_has_usage(session, packaging.id):
        raise ValueError("Единицу измерения нельзя изменить: упаковка уже использовалась в операциях")

    packaging.name = cleaned_name
    packaging.unit = unit
    packaging.comment = _clean_optional_text(comment)
    session.flush()
    return packaging


def update_consumable(
    session: Session,
    consumable_id: int,
    *,
    name: str,
    unit: Unit,
    comment: str | None = None,
) -> Consumable:
    """Update a consumable, blocking unit changes after operational usage."""

    consumable = _get_required(session, Consumable, consumable_id)
    cleaned_name = _clean_required_text(name, "Название")
    _ensure_unique_text(
        session,
        Consumable,
        "name",
        cleaned_name,
        "Расходник с таким названием уже существует",
        current_id=consumable.id,
    )

    if consumable.unit_id != unit.id and _consumable_has_usage(session, consumable.id):
        raise ValueError("Единицу измерения нельзя изменить: расходник уже использовался в операциях")

    consumable.name = cleaned_name
    consumable.unit = unit
    consumable.comment = _clean_optional_text(comment)
    session.flush()
    return consumable


def delete_unit(session: Session, unit_id: int) -> None:
    """Delete an unused measurement unit."""

    unit = _get_required(session, Unit, unit_id)
    if _unit_has_usage(session, unit.id):
        raise ValueError("Единицу измерения нельзя удалить: она уже используется в справочниках или операциях")
    session.delete(unit)
    session.flush()


def delete_product(session: Session, product_id: int) -> None:
    """Delete an unused product."""

    product = _get_required(session, Product, product_id)
    if _product_has_usage(session, product.id):
        raise ValueError("Продукт нельзя удалить: он уже используется в производстве или заказах")
    session.delete(product)
    session.flush()


def delete_preparation_type(session: Session, preparation_type_id: int) -> None:
    """Delete an unused preparation type."""

    preparation_type = _get_required(session, PreparationType, preparation_type_id)
    if _preparation_type_has_usage(session, preparation_type.id):
        raise ValueError("Вид заготовки нельзя удалить: он уже используется в заготовках")
    session.delete(preparation_type)
    session.flush()


def delete_ingredient(session: Session, ingredient_id: int) -> None:
    """Delete an unused ingredient."""

    ingredient = _get_required(session, Ingredient, ingredient_id)
    if _ingredient_has_usage(session, ingredient.id):
        raise ValueError("Ингредиент нельзя удалить: он уже используется в операциях")
    session.delete(ingredient)
    session.flush()


def delete_packaging(session: Session, packaging_id: int) -> None:
    """Delete unused packaging."""

    packaging = _get_required(session, Packaging, packaging_id)
    if _packaging_has_usage(session, packaging.id):
        raise ValueError("Упаковку нельзя удалить: она уже используется в операциях")
    session.delete(packaging)
    session.flush()


def delete_consumable(session: Session, consumable_id: int) -> None:
    """Delete an unused consumable."""

    consumable = _get_required(session, Consumable, consumable_id)
    if _consumable_has_usage(session, consumable.id):
        raise ValueError("Расходник нельзя удалить: он уже используется в операциях")
    session.delete(consumable)
    session.flush()


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


def list_consumables(session: Session) -> list[Consumable]:
    """Return consumables ordered by name."""

    return list(session.scalars(select(Consumable).order_by(Consumable.name)))
