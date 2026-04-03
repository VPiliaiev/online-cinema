from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime
from enum import Enum
from decimal import Decimal


class OrderStatusEnum(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    CANCELED = "canceled"


class OrderItemBase(BaseModel):
    movie_id: int
    price_at_order: Decimal


class OrderItemCreate(OrderItemBase):
    pass


class OrderItem(OrderItemBase):
    id: int
    order_id: int

    model_config = ConfigDict(from_attributes=True)


class OrderBase(BaseModel):
    status: OrderStatusEnum = OrderStatusEnum.PENDING
    total_amount: Optional[Decimal] = None


class OrderCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Order(OrderBase):
    id: int
    user_id: int
    created_at: datetime
    items: List[OrderItem] = []

    model_config = ConfigDict(from_attributes=True)


class OrderUpdateStatus(BaseModel):
    status: OrderStatusEnum
