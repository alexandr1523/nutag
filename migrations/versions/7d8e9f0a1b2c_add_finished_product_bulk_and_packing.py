"""add_finished_product_bulk_and_packing

Revision ID: 7d8e9f0a1b2c
Revises: 5f8c2a7b9d01
Create Date: 2026-06-20 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7d8e9f0a1b2c"
down_revision: Union[str, Sequence[str], None] = "5f8c2a7b9d01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.create_table(
        "finished_product_bulk_outputs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("unit_id", sa.Integer(), nullable=False),
        sa.Column("frozen_on", sa.Date(), nullable=True),
        sa.Column("use_by", sa.Date(), nullable=True),
        sa.Column("storage_place", sa.String(length=128), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["production_batches.id"]),
        sa.ForeignKeyConstraint(["unit_id"], ["units.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "finished_product_packings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("packed_on", sa.Date(), nullable=False),
        sa.Column("source_bulk_output_id", sa.Integer(), nullable=False),
        sa.Column("finished_output_id", sa.Integer(), nullable=False),
        sa.Column("packaging_id", sa.Integer(), nullable=False),
        sa.Column("packaging_purchase_item_id", sa.Integer(), nullable=True),
        sa.Column("packaging_unit_id", sa.Integer(), nullable=False),
        sa.Column("packaging_quantity", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("packaging_unit_cost", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("packaging_total_cost", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("total_cost", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("unit_cost", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["finished_output_id"], ["finished_product_outputs.id"]),
        sa.ForeignKeyConstraint(["packaging_id"], ["packaging.id"]),
        sa.ForeignKeyConstraint(["packaging_purchase_item_id"], ["purchase_items.id"]),
        sa.ForeignKeyConstraint(["packaging_unit_id"], ["units.id"]),
        sa.ForeignKeyConstraint(["source_bulk_output_id"], ["finished_product_bulk_outputs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_table("finished_product_packings")
    op.drop_table("finished_product_bulk_outputs")
