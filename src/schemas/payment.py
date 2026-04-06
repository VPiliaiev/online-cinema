from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from enum import Enum
from decimal import Decimal


class PaymentStatusEnum(str, Enum):
    PENDING = "pending"
    SUCCESSFUL = "successful"
    CANCELED = "canceled"
    REFUNDED = "refunded"


class PaymentItemBase(BaseModel):
    order_item_id: int
    price_at_payment: Decimal


class PaymentItem(PaymentItemBase):
    id: int
    payment_id: int

    model_config = {
        "from_attributes": True,
    }


class PaymentBase(BaseModel):
    status: PaymentStatusEnum = PaymentStatusEnum.PENDING
    amount: Decimal
    external_payment_id: Optional[str] = None


class PaymentCreate(BaseModel):
    order_id: int
    amount: Decimal
    external_payment_id: Optional[str] = None


class Payment(PaymentBase):
    id: int
    user_id: int
    order_id: int
    created_at: datetime
    items: List[PaymentItem] = []

    model_config = {
        "from_attributes": True,
    }


class StripeSessionResponse(BaseModel):
    order_id: int
    checkout_url: str
    payment_id: int
