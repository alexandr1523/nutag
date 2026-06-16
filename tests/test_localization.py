from nutag.db.models import PurchaseItemType, OrderStatus, PaymentStatus, ReservationStatus
from nutag.services.inventory import ExtendedItemType

def test_russian_enum_values():
    """Verify that core enum values are in Russian as requested."""
    
    # Purchase Item Types
    assert PurchaseItemType.INGREDIENT == "Ингредиент"
    assert PurchaseItemType.PACKAGING == "Упаковка"
    assert PurchaseItemType.CONSUMABLE == "Расходник"
    
    # Order Statuses
    assert OrderStatus.NEW == "Новый"
    assert OrderStatus.CONFIRMED == "Подтвержден"
    assert OrderStatus.READY == "Готов"
    assert OrderStatus.DELIVERED == "Выдан"
    assert OrderStatus.CANCELLED == "Отменен"
    
    # Payment Statuses
    assert PaymentStatus.PENDING == "Ожидает"
    assert PaymentStatus.PAID == "Оплачен"
    assert PaymentStatus.ON_DELIVERY == "При получении"
    assert PaymentStatus.REFUNDED == "Возврат"
    
    # Reservation Statuses
    assert ReservationStatus.NOT_RESERVED == "Не зарезервирован"
    assert ReservationStatus.RESERVED == "Зарезервирован"
    
    # Extended Inventory Types
    assert ExtendedItemType.PREPARATION == "Заготовка"
    assert ExtendedItemType.PRODUCT == "Готовый продукт"
