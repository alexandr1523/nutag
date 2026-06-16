"""migrate_item_types_to_russian

Revision ID: 039e6c70e7d1
Revises: 6baa46783c5c
Create Date: 2026-06-16 22:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '039e6c70e7d1'
down_revision: Union[str, None] = '6baa46783c5c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Map old English values to new Russian values
    mapping = {
        'ingredient': 'Ингредиент',
        'packaging': 'Упаковка',
        'consumable': 'Расходник'
    }
    
    # Update purchase_items table
    for old, new in mapping.items():
        op.execute(
            f"UPDATE purchase_items SET item_type = '{new}' WHERE item_type = '{old}'"
        )


def downgrade() -> None:
    mapping = {
        'Ингредиент': 'ingredient',
        'Упаковка': 'packaging',
        'Расходник': 'consumable'
    }
    
    for old, new in mapping.items():
        op.execute(
            f"UPDATE purchase_items SET item_type = '{new}' WHERE item_type = '{old}'"
        )
