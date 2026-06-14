from datetime import date
from decimal import Decimal

from sqlalchemy import inspect, select

from nutag.db import create_database, create_engine_for_url, create_session_factory
from nutag.db.models import Ingredient, Packaging, Product, Purchase, PurchaseItem, PurchaseItemType, Unit


def test_create_database_creates_initial_tables() -> None:
    engine = create_engine_for_url("sqlite:///:memory:")

    create_database(engine)

    table_names = set(inspect(engine).get_table_names())
    assert {
        "units",
        "products",
        "ingredients",
        "packaging",
        "purchases",
        "purchase_items",
        "preparations",
        "preparation_ingredient_uses",
        "production_batches",
        "batch_ingredient_uses",
        "batch_preparation_uses",
        "finished_product_outputs",
    }.issubset(table_names)


def test_purchase_with_items_can_be_persisted() -> None:
    engine = create_engine_for_url("sqlite:///:memory:")
    create_database(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        kg = Unit(name="kilogram", short_name="kg")
        piece = Unit(name="piece", short_name="pcs")
        product = Product(name="Пельмени")
        flour = Ingredient(name="Мука", unit=kg)
        container = Packaging(name="Контейнер 1 кг", unit=piece)
        purchase = Purchase(
            purchase_date=date(2026, 6, 14),
            supplier="Тестовый магазин",
            purchased_by="Кристина",
            shopping_minutes=45,
            transport_cost=Decimal("100.00"),
            items=[
                PurchaseItem(
                    line_number=1,
                    item_type=PurchaseItemType.INGREDIENT,
                    ingredient=flour,
                    item_name="Мука",
                    unit=kg,
                    quantity=Decimal("2.000"),
                    unit_price=Decimal("80.00"),
                    total_price=Decimal("160.00"),
                ),
                PurchaseItem(
                    line_number=2,
                    item_type=PurchaseItemType.PACKAGING,
                    packaging=container,
                    item_name="Контейнер 1 кг",
                    unit=piece,
                    quantity=Decimal("10.000"),
                    unit_price=Decimal("12.00"),
                    total_price=Decimal("120.00"),
                ),
            ],
        )
        session.add_all([kg, piece, product, purchase])
        session.commit()

    with session_factory() as session:
        saved_purchase = session.scalar(select(Purchase).where(Purchase.supplier == "Тестовый магазин"))
        assert saved_purchase is not None
        assert len(saved_purchase.items) == 2
        assert saved_purchase.items[0].ingredient is not None
        assert saved_purchase.items[1].packaging is not None
