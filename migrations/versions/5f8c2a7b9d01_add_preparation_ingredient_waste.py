"""add_preparation_ingredient_waste

Revision ID: 5f8c2a7b9d01
Revises: c2e0f8f4a1b2
Create Date: 2026-06-20 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "5f8c2a7b9d01"
down_revision: Union[str, Sequence[str], None] = "c2e0f8f4a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    with op.batch_alter_table("preparation_ingredient_uses", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "waste_quantity",
                sa.Numeric(precision=12, scale=3),
                nullable=False,
                server_default="0",
            )
        )


def downgrade() -> None:
    """Downgrade schema."""

    with op.batch_alter_table("preparation_ingredient_uses", schema=None) as batch_op:
        batch_op.drop_column("waste_quantity")
