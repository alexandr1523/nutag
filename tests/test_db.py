from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import inspect, select, text

from nutag.db import (
    create_app_database,
    create_database,
    create_engine_for_url,
    create_session_factory,
    default_sqlite_path,
    initialize_database,
)
from nutag.db.models import Ingredient, Packaging, Product, Purchase, PurchaseItem, PurchaseItemType, Unit


def test_create_database_creates_initial_tables() -> None:
    engine = create_engine_for_url("sqlite:///:memory:")

    create_database(engine)

    table_names = set(inspect(engine).get_table_names())
    assert {
        "units",
        "products",
        "preparation_types",
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


def test_create_app_database_initializes_schema_and_session_factory() -> None:
    engine, session_factory = create_app_database("sqlite:///:memory:")

    table_names = set(inspect(engine).get_table_names())
    assert "units" in table_names

    with session_factory() as session:
        session.add(Unit(name="kilogram", short_name="kg"))
        session.commit()

    with session_factory() as session:
        saved_unit = session.scalar(select(Unit).where(Unit.short_name == "kg"))
        assert saved_unit is not None
        assert saved_unit.name == "kilogram"


def test_create_engine_uses_database_url_env(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "configured" / "nutag.sqlite3"
    monkeypatch.setenv("NUTAG_DATABASE_URL", f"sqlite:///{db_path}")

    engine = create_engine_for_url()

    assert engine.url.database == str(db_path)
    assert db_path.parent.exists()


def test_default_sqlite_path_uses_user_data_directory(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("NUTAG_DATABASE_URL", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))

    path = default_sqlite_path()

    assert path.name == "nutag.sqlite3"
    assert path.parent.name == "Nutag"
    assert not path.is_relative_to(Path.cwd())


def test_create_engine_copies_legacy_project_sqlite_to_user_data(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("NUTAG_DATABASE_URL", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))

    legacy_path = tmp_path / "nutag.sqlite3"
    legacy_path.write_bytes(b"legacy database")

    create_engine_for_url()

    copied_path = default_sqlite_path()
    assert copied_path.exists()
    assert copied_path.read_bytes() == b"legacy database"
    assert legacy_path.exists()


def test_initialize_database_upgrades_legacy_sqlite_without_alembic(tmp_path) -> None:
    db_path = tmp_path / "legacy.sqlite3"
    engine = create_engine_for_url(f"sqlite:///{db_path}")

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE units (
                    id INTEGER NOT NULL PRIMARY KEY,
                    name VARCHAR(64) NOT NULL UNIQUE,
                    short_name VARCHAR(16) NOT NULL UNIQUE,
                    comment TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE purchase_items (
                    id INTEGER NOT NULL PRIMARY KEY,
                    purchase_id INTEGER NOT NULL,
                    line_number INTEGER NOT NULL,
                    item_type VARCHAR(32) NOT NULL,
                    ingredient_id INTEGER,
                    packaging_id INTEGER,
                    item_name VARCHAR(128) NOT NULL,
                    unit_id INTEGER NOT NULL,
                    quantity NUMERIC(12, 3) NOT NULL,
                    unit_price NUMERIC(12, 2) NOT NULL,
                    total_price NUMERIC(12, 2) NOT NULL,
                    expires_on DATE,
                    comment TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE production_batches (
                    id INTEGER NOT NULL PRIMARY KEY,
                    produced_on DATE NOT NULL,
                    product_id INTEGER NOT NULL,
                    actual_output_quantity NUMERIC(12, 3) NOT NULL,
                    output_unit_id INTEGER NOT NULL,
                    labor_cost NUMERIC(12, 2) NOT NULL,
                    allocated_overhead NUMERIC(12, 2) NOT NULL,
                    total_cost NUMERIC(12, 2) NOT NULL,
                    unit_cost NUMERIC(12, 4) NOT NULL,
                    status VARCHAR(32) NOT NULL,
                    comment TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
                )
                """
            )
        )

    initialize_database(engine)

    inspector = inspect(engine)
    backups = list((db_path.parent / "backups").glob("legacy.before-initialization.*.sqlite3"))
    assert len(backups) == 1
    assert "alembic_version" in inspector.get_table_names()
    assert "consumables" in inspector.get_table_names()
    assert "orders" in inspector.get_table_names()

    purchase_item_columns = {column["name"] for column in inspector.get_columns("purchase_items")}
    assert "consumable_id" in purchase_item_columns

    production_batch_columns = {column["name"] for column in inspector.get_columns("production_batches")}
    assert {"planned_quantity", "waste_quantity", "equipment_depreciation"}.issubset(production_batch_columns)


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
