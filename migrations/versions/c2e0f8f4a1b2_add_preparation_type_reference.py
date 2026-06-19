"""add_preparation_type_reference

Revision ID: c2e0f8f4a1b2
Revises: 039e6c70e7d1
Create Date: 2026-06-20 15:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "c2e0f8f4a1b2"
down_revision: Union[str, Sequence[str], None] = "039e6c70e7d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    bind = op.get_bind()
    inspector = inspect(bind)

    if "preparation_types" not in inspector.get_table_names():
        op.create_table(
            "preparation_types",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("comment", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name"),
        )

    preparation_columns = {column["name"] for column in inspector.get_columns("preparations")}
    if "preparation_type_id" not in preparation_columns:
        with op.batch_alter_table("preparations", schema=None) as batch_op:
            batch_op.add_column(sa.Column("preparation_type_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                "fk_preparations_preparation_type",
                "preparation_types",
                ["preparation_type_id"],
                ["id"],
            )


def downgrade() -> None:
    """Downgrade schema."""

    with op.batch_alter_table("preparations", schema=None) as batch_op:
        batch_op.drop_constraint("fk_preparations_preparation_type", type_="foreignkey")
        batch_op.drop_column("preparation_type_id")

    op.drop_table("preparation_types")
