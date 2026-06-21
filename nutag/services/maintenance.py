"""Service functions for data maintenance and resetting."""

from __future__ import annotations

from sqlalchemy import delete
from sqlalchemy.orm import Session

from nutag.db.models import (
    BatchIngredientUse,
    BatchPackagingUse,
    BatchPreparationUse,
    FinishedProductBulkOutput,
    FinishedProductOutput,
    FinishedProductPacking,
    Order,
    OrderItem,
    Preparation,
    PreparationIngredientUse,
    ProductionBatch,
    Purchase,
    PurchaseItem,
    FixedExpense
)

def reset_operational_data(session: Session) -> None:
    """Delete all operational data while preserving core dictionaries.
    
    Order of deletion matters due to foreign key constraints.
    """
    
    # 1. Order related
    session.execute(delete(OrderItem))
    session.execute(delete(Order))
    
    # 2. Production related
    session.execute(delete(FinishedProductPacking))
    session.execute(delete(FinishedProductOutput))
    session.execute(delete(FinishedProductBulkOutput))
    session.execute(delete(BatchIngredientUse))
    session.execute(delete(BatchPreparationUse))
    session.execute(delete(BatchPackagingUse))
    session.execute(delete(ProductionBatch))
    
    # 3. Preparation related
    session.execute(delete(PreparationIngredientUse))
    session.execute(delete(Preparation))
    
    # 4. Purchase related
    session.execute(delete(PurchaseItem))
    session.execute(delete(Purchase))
    
    # 5. Other transaction data
    session.execute(delete(FixedExpense))
    
    session.commit()
