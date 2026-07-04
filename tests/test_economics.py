from datetime import date
from decimal import Decimal

from nutag.db import create_database, create_engine_for_url, create_session_factory
from nutag.db.models import PurchaseItemType
from nutag.services.economics import list_finished_product_cost_reports
from nutag.services.packing import pack_finished_product
from nutag.services.production import BatchIngredientInput, create_production_batch
from nutag.services.purchases import PurchaseLineInput, create_purchase
from nutag.services.references import create_ingredient, create_packaging, create_product, create_unit


def make_session_factory():
    engine = create_engine_for_url("sqlite:///:memory:")
    create_database(engine)
    return create_session_factory(engine)


def test_finished_product_cost_report_uses_traceable_direct_costs() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="kilogram", short_name="kg")
        piece = create_unit(session, name="piece", short_name="pcs")
        flour = create_ingredient(session, name="Мука", unit=kg)
        product = create_product(session, name="Пельмени")
        container = create_packaging(session, name="Контейнер", unit=piece)
        purchase = create_purchase(
            session,
            purchase_date=date(2026, 6, 14),
            lines=[
                PurchaseLineInput(
                    item_type=PurchaseItemType.INGREDIENT,
                    ingredient=flour,
                    item_name=flour.name,
                    unit=kg,
                    quantity="5",
                    unit_price="80",
                ),
                PurchaseLineInput(
                    item_type=PurchaseItemType.PACKAGING,
                    packaging=container,
                    item_name=container.name,
                    unit=piece,
                    quantity="10",
                    unit_price="5",
                ),
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
            labor_cost="300",
        )
        packing = pack_finished_product(
            session,
            packed_on=date(2026, 6, 16),
            source_bulk_output_id=batch.bulk_outputs[0].id,
            packaging=container,
            packaging_unit=piece,
            packaging_purchase_item_id=purchase.items[1].id,
            package_size="0.5",
            package_unit=kg,
            package_count=4,
        )
        session.commit()
        packing_id = packing.id

    with session_factory() as session:
        reports = list_finished_product_cost_reports(session)

    assert len(reports) == 1
    report = reports[0]
    assert report.packing_id == packing_id
    assert report.product_name == "Пельмени"
    assert report.ingredient_cost == Decimal("160.000")
    assert report.labor_cost == Decimal("300.00")
    assert report.packaging_cost == Decimal("20.00")
    assert report.unpacked_output_cost == Decimal("460.000")
    assert report.total_direct_cost == Decimal("480.000")
    assert report.cost_per_package == Decimal("120.000")
    assert report.cost_per_base_unit == Decimal("240.00")
    assert "Амортизация" in report.excluded_components
