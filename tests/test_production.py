from datetime import date
from decimal import Decimal

import pytest

from nutag.db import create_database, create_engine_for_url, create_session_factory
from nutag.db.models import PurchaseItemType
from nutag.services.inventory import (
    list_available_bulk_finished_product_outputs,
    list_available_finished_product_outputs,
    list_available_stock_batches,
)
from nutag.services.packing import pack_finished_product
from nutag.services.preparations import PreparationIngredientInput, create_preparation
from nutag.services.production import (
    BatchIngredientInput,
    BatchPreparationInput,
    calculate_output_total,
    create_production_batch,
    delete_production_batch,
    is_production_batch_used,
    list_production_batches,
    update_production_batch,
)
from nutag.services.purchases import PurchaseLineInput, create_purchase
from nutag.services.references import (
    create_ingredient,
    create_packaging,
    create_preparation_type,
    create_product,
    create_unit,
)


def make_session_factory():
    engine = create_engine_for_url("sqlite:///:memory:")
    create_database(engine)
    return create_session_factory(engine)


def test_calculate_output_total_validates_package_size_and_count() -> None:
    assert calculate_output_total(package_size="0.5", package_count=12) == Decimal("6.0")

    with pytest.raises(ValueError, match="Package size"):
        calculate_output_total(package_size="0", package_count=12)

    with pytest.raises(ValueError, match="Package count"):
        calculate_output_total(package_size="0.5", package_count=0)


def test_create_production_batch_calculates_costs_and_bulk_output() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="kilogram", short_name="kg")
        product = create_product(session, name="Пельмени")
        flour = create_ingredient(session, name="Мука", unit=kg)
        meat = create_ingredient(session, name="Фарш", unit=kg)
        filling = create_preparation_type(session, name="Начинка")
        preparation = create_preparation(
            session,
            prepared_on=date(2026, 6, 14),
            preparation_type=filling,
            output_quantity="4",
            output_unit=kg,
            ingredient_uses=[PreparationIngredientInput(ingredient=meat, unit=kg, quantity="4", unit_cost="450")],
        )

        batch = create_production_batch(
            session,
            produced_on=date(2026, 6, 15),
            product=product,
            planned_quantity="5",
            actual_output_quantity="6",
            output_unit=kg,
            ingredient_uses=[BatchIngredientInput(ingredient=flour, unit=kg, quantity="2", unit_cost="92")],
            preparation_uses=[
                BatchPreparationInput(
                    preparation=preparation,
                    unit=kg,
                    quantity="3",
                    unit_cost=preparation.unit_cost,
                )
            ],
            labor_cost="500",
            equipment_depreciation="40",
            allocated_overhead="60",
        )
        session.commit()
        batch_id = batch.id

    with session_factory() as session:
        saved = list_production_batches(session)[0]
        assert saved.id == batch_id
        assert saved.total_cost == Decimal("2134.00")
        assert saved.unit_cost == Decimal("355.6667")
        assert len(saved.ingredient_uses) == 1
        assert saved.ingredient_uses[0].total_cost == Decimal("184.00")
        assert len(saved.preparation_uses) == 1
        assert saved.preparation_uses[0].total_cost == Decimal("1350.00")
        assert saved.outputs == []
        assert len(saved.bulk_outputs) == 1
        assert saved.bulk_outputs[0].quantity == Decimal("6.000")


def test_create_production_batch_rejects_zero_output_quantity() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="kilogram", short_name="kg")
        product = create_product(session, name="Пельмени")
        with pytest.raises(ValueError, match="actual output"):
            create_production_batch(
                session,
                produced_on=date(2026, 6, 15),
                product=product,
                actual_output_quantity="0",
                output_unit=kg,
                labor_cost="1",
            )


def test_create_production_batch_rejects_zero_labor_cost() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="kilogram", short_name="kg")
        product = create_product(session, name="Пельмени")
        with pytest.raises(ValueError, match="labor cost"):
            create_production_batch(
                session,
                produced_on=date(2026, 6, 15),
                product=product,
                actual_output_quantity="1",
                output_unit=kg,
                labor_cost="0",
            )


def test_create_production_batch_allows_unpacked_output_without_packaged_lines() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="kilogram", short_name="kg")
        product = create_product(session, name="Пельмени")
        batch = create_production_batch(
            session,
            produced_on=date(2026, 6, 15),
            product=product,
            actual_output_quantity="1",
            output_unit=kg,
            labor_cost="1",
        )
        session.commit()

        assert batch.outputs == []
        assert len(batch.bulk_outputs) == 1
        assert batch.bulk_outputs[0].quantity == Decimal("1.000")


def test_create_production_batch_creates_full_unpacked_output() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="kilogram", short_name="kg")
        product = create_product(session, name="Пельмени")
        create_production_batch(
            session,
            produced_on=date(2026, 6, 15),
            product=product,
            actual_output_quantity="5",
            output_unit=kg,
            labor_cost="1",
        )
        session.commit()

    with session_factory() as session:
        bulk_outputs = list_available_bulk_finished_product_outputs(session)

    assert len(bulk_outputs) == 1
    assert bulk_outputs[0].product_name == "Пельмени"
    assert bulk_outputs[0].current_quantity == Decimal("5.000")


def test_create_production_batch_persists_selected_source_batch_ids() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="kilogram", short_name="kg")
        product = create_product(session, name="Пельмени")
        flour = create_ingredient(session, name="Мука", unit=kg)
        meat = create_ingredient(session, name="Фарш", unit=kg)
        filling = create_preparation_type(session, name="Начинка")

        purchase = create_purchase(
            session,
            purchase_date=date(2026, 6, 13),
            lines=[
                PurchaseLineInput(
                    item_type=PurchaseItemType.INGREDIENT,
                    item_name=flour.name,
                    ingredient=flour,
                    unit=kg,
                    quantity="10",
                    unit_price="92",
                )
            ],
        )
        ingredient_purchase_item = purchase.items[0]
        preparation = create_preparation(
            session,
            prepared_on=date(2026, 6, 14),
            preparation_type=filling,
            output_quantity="4",
            output_unit=kg,
            ingredient_uses=[PreparationIngredientInput(ingredient=meat, unit=kg, quantity="4", unit_cost="450")],
        )

        batch = create_production_batch(
            session,
            produced_on=date(2026, 6, 15),
            product=product,
            actual_output_quantity="6",
            output_unit=kg,
            ingredient_uses=[
                BatchIngredientInput(
                    ingredient=flour,
                    unit=kg,
                    quantity="2",
                    unit_cost="92",
                    purchase_item_id=ingredient_purchase_item.id,
                )
            ],
            preparation_uses=[
                BatchPreparationInput(
                    preparation=preparation,
                    unit=kg,
                    quantity="3",
                    unit_cost=preparation.unit_cost,
                    source_preparation_id=preparation.id,
                )
            ],
            labor_cost="1",
        )
        session.commit()
        batch_id = batch.id

    with session_factory() as session:
        saved = list_production_batches(session)[0]
        assert saved.id == batch_id
        assert saved.ingredient_uses[0].purchase_item_id == ingredient_purchase_item.id
        assert saved.preparation_uses[0].source_preparation_id == preparation.id
        assert saved.packaging_uses == []
        assert saved.bulk_outputs[0].quantity == Decimal("6.000")


def test_create_production_batch_uses_selected_source_prices() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="kilogram", short_name="kg")
        product = create_product(session, name="Пельмени")
        flour = create_ingredient(session, name="Мука", unit=kg)
        meat = create_ingredient(session, name="Фарш", unit=kg)
        filling = create_preparation_type(session, name="Начинка")

        purchase = create_purchase(
            session,
            purchase_date=date(2026, 6, 13),
            lines=[
                PurchaseLineInput(
                    item_type=PurchaseItemType.INGREDIENT,
                    ingredient=flour,
                    item_name=flour.name,
                    unit=kg,
                    quantity="10",
                    unit_price="80",
                )
            ],
        )
        preparation = create_preparation(
            session,
            prepared_on=date(2026, 6, 14),
            preparation_type=filling,
            output_quantity="4",
            output_unit=kg,
            ingredient_uses=[PreparationIngredientInput(ingredient=meat, unit=kg, quantity="4", unit_cost="100")],
        )

        batch = create_production_batch(
            session,
            produced_on=date(2026, 6, 15),
            product=product,
            actual_output_quantity="1",
            output_unit=kg,
            ingredient_uses=[
                BatchIngredientInput(
                    ingredient=flour,
                    unit=kg,
                    quantity="2",
                    unit_cost="999",
                    purchase_item_id=purchase.items[0].id,
                )
            ],
            preparation_uses=[
                BatchPreparationInput(
                    preparation=preparation,
                    unit=kg,
                    quantity="2",
                    unit_cost="999",
                    source_preparation_id=preparation.id,
                )
            ],
            labor_cost="1",
        )
        session.commit()

        assert batch.ingredient_uses[0].unit_cost == Decimal("80.0000")
        assert batch.ingredient_uses[0].total_cost == Decimal("160.00")
        assert batch.preparation_uses[0].unit_cost == Decimal("100.0000")
        assert batch.preparation_uses[0].total_cost == Decimal("200.00")
        assert batch.packaging_uses == []
        assert batch.total_cost == Decimal("361.00")


def test_update_production_batch_recalculates_unused_batch_and_stock() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="kilogram", short_name="kg")
        product = create_product(session, name="Пельмени")
        flour = create_ingredient(session, name="Мука", unit=kg)
        purchase = create_purchase(
            session,
            purchase_date=date(2026, 6, 13),
            lines=[
                PurchaseLineInput(
                    item_type=PurchaseItemType.INGREDIENT,
                    ingredient=flour,
                    item_name=flour.name,
                    unit=kg,
                    quantity="5",
                    unit_price="80",
                )
            ],
        )
        batch = create_production_batch(
            session,
            produced_on=date(2026, 6, 15),
            product=product,
            actual_output_quantity="2",
            output_unit=kg,
            ingredient_uses=[
                BatchIngredientInput(
                    ingredient=flour,
                    unit=kg,
                    quantity="2",
                    unit_cost="999",
                    purchase_item_id=purchase.items[0].id,
                )
            ],
            labor_cost="100",
        )
        batch_id = batch.id

        updated = update_production_batch(
            session,
            batch_id,
            produced_on=date(2026, 6, 16),
            product=product,
            actual_output_quantity="3",
            output_unit=kg,
            ingredient_uses=[
                BatchIngredientInput(
                    ingredient=flour,
                    unit=kg,
                    quantity="3",
                    unit_cost="999",
                    purchase_item_id=purchase.items[0].id,
                )
            ],
            labor_cost="120",
            allocated_overhead="30",
            comment="Исправлено",
        )
        session.commit()

        assert updated.id == batch_id
        assert updated.produced_on == date(2026, 6, 16)
        assert updated.actual_output_quantity == Decimal("3.000")
        assert updated.labor_cost == Decimal("120.00")
        assert updated.allocated_overhead == Decimal("30.00")
        assert updated.total_cost == Decimal("390.00")
        assert updated.unit_cost == Decimal("130.0000")
        assert updated.comment == "Исправлено"
        assert len(updated.ingredient_uses) == 1
        assert updated.ingredient_uses[0].quantity == Decimal("3.000")
        assert updated.ingredient_uses[0].unit_cost == Decimal("80.0000")
        assert updated.bulk_outputs[0].quantity == Decimal("3.000")

        stock = [
            stock_batch
            for stock_batch in list_available_stock_batches(session)
            if stock_batch.batch_type == "purchase" and stock_batch.batch_id == purchase.items[0].id
        ][0]
        assert stock.current_quantity == Decimal("2.000")


def test_update_production_batch_allows_current_batch_reserved_quantity() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="kilogram", short_name="kg")
        product = create_product(session, name="Пельмени")
        flour = create_ingredient(session, name="Мука", unit=kg)
        purchase = create_purchase(
            session,
            purchase_date=date(2026, 6, 13),
            lines=[
                PurchaseLineInput(
                    item_type=PurchaseItemType.INGREDIENT,
                    ingredient=flour,
                    item_name=flour.name,
                    unit=kg,
                    quantity="2",
                    unit_price="80",
                )
            ],
        )
        batch = create_production_batch(
            session,
            produced_on=date(2026, 6, 15),
            product=product,
            actual_output_quantity="2",
            output_unit=kg,
            ingredient_uses=[
                BatchIngredientInput(
                    ingredient=flour,
                    unit=kg,
                    quantity="2",
                    unit_cost="999",
                    purchase_item_id=purchase.items[0].id,
                )
            ],
            labor_cost="1",
        )

        updated = update_production_batch(
            session,
            batch.id,
            produced_on=date(2026, 6, 15),
            product=product,
            actual_output_quantity="2",
            output_unit=kg,
            ingredient_uses=[
                BatchIngredientInput(
                    ingredient=flour,
                    unit=kg,
                    quantity="2",
                    unit_cost="999",
                    purchase_item_id=purchase.items[0].id,
                )
            ],
            labor_cost="1",
        )

        assert updated.ingredient_uses[0].quantity == Decimal("2.000")
        assert updated.total_cost == Decimal("161.00")


def test_update_production_batch_rejects_selected_purchase_overdraft_excluding_current_batch() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="kilogram", short_name="kg")
        product = create_product(session, name="Пельмени")
        flour = create_ingredient(session, name="Мука", unit=kg)
        purchase = create_purchase(
            session,
            purchase_date=date(2026, 6, 13),
            lines=[
                PurchaseLineInput(
                    item_type=PurchaseItemType.INGREDIENT,
                    ingredient=flour,
                    item_name=flour.name,
                    unit=kg,
                    quantity="2",
                    unit_price="80",
                )
            ],
        )
        batch = create_production_batch(
            session,
            produced_on=date(2026, 6, 15),
            product=product,
            actual_output_quantity="1",
            output_unit=kg,
            ingredient_uses=[
                BatchIngredientInput(
                    ingredient=flour,
                    unit=kg,
                    quantity="1",
                    unit_cost="999",
                    purchase_item_id=purchase.items[0].id,
                )
            ],
            labor_cost="1",
        )
        create_production_batch(
            session,
            produced_on=date(2026, 6, 16),
            product=product,
            actual_output_quantity="1",
            output_unit=kg,
            ingredient_uses=[
                BatchIngredientInput(
                    ingredient=flour,
                    unit=kg,
                    quantity="0.5",
                    unit_cost="999",
                    purchase_item_id=purchase.items[0].id,
                )
            ],
            labor_cost="1",
        )

        with pytest.raises(ValueError, match="Недостаточно остатка"):
            update_production_batch(
                session,
                batch.id,
                produced_on=date(2026, 6, 17),
                product=product,
                actual_output_quantity="2",
                output_unit=kg,
                ingredient_uses=[
                    BatchIngredientInput(
                        ingredient=flour,
                        unit=kg,
                        quantity="2",
                        unit_cost="999",
                        purchase_item_id=purchase.items[0].id,
                    )
                ],
                labor_cost="1",
            )


def test_update_production_batch_rejects_batch_used_in_packing() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="kilogram", short_name="kg")
        piece = create_unit(session, name="piece", short_name="pcs")
        product = create_product(session, name="Пельмени")
        container = create_packaging(session, name="Контейнер", unit=piece)
        purchase = create_purchase(
            session,
            purchase_date=date(2026, 6, 14),
            lines=[
                PurchaseLineInput(
                    item_type=PurchaseItemType.PACKAGING,
                    packaging=container,
                    item_name=container.name,
                    unit=piece,
                    quantity="10",
                    unit_price="5",
                )
            ],
        )
        batch = create_production_batch(
            session,
            produced_on=date(2026, 6, 15),
            product=product,
            actual_output_quantity="3",
            output_unit=kg,
            labor_cost="300",
        )
        pack_finished_product(
            session,
            packed_on=date(2026, 6, 16),
            source_bulk_output_id=batch.bulk_outputs[0].id,
            packaging=container,
            packaging_unit=piece,
            packaging_purchase_item_id=purchase.items[0].id,
            package_size="0.5",
            package_unit=kg,
            package_count=2,
        )

        assert is_production_batch_used(session, batch.id)
        with pytest.raises(ValueError, match="уже использована в фасовке"):
            update_production_batch(
                session,
                batch.id,
                produced_on=date(2026, 6, 17),
                product=product,
                actual_output_quantity="3",
                output_unit=kg,
                labor_cost="300",
            )


def test_delete_production_batch_removes_unused_batch_and_restores_stock() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="kilogram", short_name="kg")
        product = create_product(session, name="Пельмени")
        flour = create_ingredient(session, name="Мука", unit=kg)
        purchase = create_purchase(
            session,
            purchase_date=date(2026, 6, 13),
            lines=[
                PurchaseLineInput(
                    item_type=PurchaseItemType.INGREDIENT,
                    ingredient=flour,
                    item_name=flour.name,
                    unit=kg,
                    quantity="5",
                    unit_price="80",
                )
            ],
        )
        batch = create_production_batch(
            session,
            produced_on=date(2026, 6, 15),
            product=product,
            actual_output_quantity="2",
            output_unit=kg,
            ingredient_uses=[
                BatchIngredientInput(
                    ingredient=flour,
                    unit=kg,
                    quantity="2",
                    unit_cost="999",
                    purchase_item_id=purchase.items[0].id,
                )
            ],
            labor_cost="100",
        )
        batch_id = batch.id
        bulk_output_id = batch.bulk_outputs[0].id

        stock_before_delete = [
            stock_batch
            for stock_batch in list_available_stock_batches(session)
            if stock_batch.batch_type == "purchase" and stock_batch.batch_id == purchase.items[0].id
        ][0]
        assert stock_before_delete.current_quantity == Decimal("3.000")

        delete_production_batch(session, batch_id)
        session.commit()

        assert list_production_batches(session) == []
        assert [
            bulk_output
            for bulk_output in list_available_bulk_finished_product_outputs(session)
            if bulk_output.bulk_output_id == bulk_output_id
        ] == []
        stock_after_delete = [
            stock_batch
            for stock_batch in list_available_stock_batches(session)
            if stock_batch.batch_type == "purchase" and stock_batch.batch_id == purchase.items[0].id
        ][0]
        assert stock_after_delete.current_quantity == Decimal("5.000")


def test_delete_production_batch_rejects_batch_used_in_packing() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="kilogram", short_name="kg")
        piece = create_unit(session, name="piece", short_name="pcs")
        product = create_product(session, name="Пельмени")
        container = create_packaging(session, name="Контейнер", unit=piece)
        purchase = create_purchase(
            session,
            purchase_date=date(2026, 6, 14),
            lines=[
                PurchaseLineInput(
                    item_type=PurchaseItemType.PACKAGING,
                    packaging=container,
                    item_name=container.name,
                    unit=piece,
                    quantity="10",
                    unit_price="5",
                )
            ],
        )
        batch = create_production_batch(
            session,
            produced_on=date(2026, 6, 15),
            product=product,
            actual_output_quantity="3",
            output_unit=kg,
            labor_cost="300",
        )
        pack_finished_product(
            session,
            packed_on=date(2026, 6, 16),
            source_bulk_output_id=batch.bulk_outputs[0].id,
            packaging=container,
            packaging_unit=piece,
            packaging_purchase_item_id=purchase.items[0].id,
            package_size="0.5",
            package_unit=kg,
            package_count=2,
        )

        with pytest.raises(ValueError, match="уже использована в фасовке"):
            delete_production_batch(session, batch.id)


def test_create_production_batch_rejects_selected_preparation_overdraft() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="kilogram", short_name="kg")
        product = create_product(session, name="Пельмени")
        meat = create_ingredient(session, name="Фарш", unit=kg)
        filling = create_preparation_type(session, name="Начинка")
        preparation = create_preparation(
            session,
            prepared_on=date(2026, 6, 14),
            preparation_type=filling,
            output_quantity="1",
            output_unit=kg,
            ingredient_uses=[PreparationIngredientInput(ingredient=meat, unit=kg, quantity="1", unit_cost="100")],
        )

        with pytest.raises(ValueError, match="Недостаточно остатка"):
            create_production_batch(
                session,
                produced_on=date(2026, 6, 15),
                product=product,
                actual_output_quantity="1",
                output_unit=kg,
                preparation_uses=[
                    BatchPreparationInput(
                        preparation=preparation,
                        unit=kg,
                        quantity="2",
                        unit_cost=preparation.unit_cost,
                        source_preparation_id=preparation.id,
                    )
                ],
                labor_cost="1",
            )


def test_pack_finished_product_consumes_unpacked_output_and_packaging() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="kilogram", short_name="kg")
        piece = create_unit(session, name="piece", short_name="pcs")
        product = create_product(session, name="Пельмени")
        container = create_packaging(session, name="Контейнер", unit=piece)
        purchase = create_purchase(
            session,
            purchase_date=date(2026, 6, 14),
            lines=[
                PurchaseLineInput(
                    item_type=PurchaseItemType.PACKAGING,
                    packaging=container,
                    item_name=container.name,
                    unit=piece,
                    quantity="10",
                    unit_price="5",
                )
            ],
        )
        batch = create_production_batch(
            session,
            produced_on=date(2026, 6, 15),
            product=product,
            actual_output_quantity="3",
            output_unit=kg,
            labor_cost="300",
        )

        packing = pack_finished_product(
            session,
            packed_on=date(2026, 6, 16),
            source_bulk_output_id=batch.bulk_outputs[0].id,
            packaging=container,
            packaging_unit=piece,
            packaging_purchase_item_id=purchase.items[0].id,
            package_size="0.5",
            package_unit=kg,
            package_count=4,
        )
        session.commit()

        assert packing.source_bulk_output_id == batch.bulk_outputs[0].id
        assert packing.finished_output.total_quantity == Decimal("2.0")
        assert packing.packaging_quantity == Decimal("4")
        assert packing.packaging_unit_cost == Decimal("5.0000")
        assert packing.packaging_total_cost == Decimal("20.00")
        assert packing.unit_cost == Decimal("110.0000")

    with session_factory() as session:
        bulk_outputs = list_available_bulk_finished_product_outputs(session)
        finished_outputs = list_available_finished_product_outputs(session)
        stock_batches = list_available_stock_batches(session)

    assert bulk_outputs[0].current_quantity == Decimal("1.000")
    assert finished_outputs[0].current_quantity == Decimal("2.000")
    assert finished_outputs[0].unit_cost == Decimal("110.0000")
    assert stock_batches[0].current_quantity == Decimal("6.000")


def test_pack_finished_product_rejects_unpacked_overdraft() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="kilogram", short_name="kg")
        piece = create_unit(session, name="piece", short_name="pcs")
        product = create_product(session, name="Пельмени")
        container = create_packaging(session, name="Контейнер", unit=piece)
        purchase = create_purchase(
            session,
            purchase_date=date(2026, 6, 14),
            lines=[
                PurchaseLineInput(
                    item_type=PurchaseItemType.PACKAGING,
                    packaging=container,
                    item_name=container.name,
                    unit=piece,
                    quantity="10",
                    unit_price="5",
                )
            ],
        )
        batch = create_production_batch(
            session,
            produced_on=date(2026, 6, 15),
            product=product,
            actual_output_quantity="1",
            output_unit=kg,
            labor_cost="1",
        )

        with pytest.raises(ValueError, match="Недостаточно нефасованного остатка"):
            pack_finished_product(
                session,
                packed_on=date(2026, 6, 16),
                source_bulk_output_id=batch.bulk_outputs[0].id,
                packaging=container,
                packaging_unit=piece,
                packaging_purchase_item_id=purchase.items[0].id,
                package_size="0.5",
                package_unit=kg,
                package_count=3,
            )
