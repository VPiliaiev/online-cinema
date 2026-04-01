from pydantic import BaseModel
from typing import List
from datetime import datetime


class CartItemBase(BaseModel):
    movie_id: int


class CartItemCreate(CartItemBase):
    pass


class CartItem(CartItemBase):
    id: int
    added_at: datetime

    model_config = {
        "from_attributes": True,
    }


class CartBase(BaseModel):
    user_id: int


class Cart(CartBase):
    id: int
    items: List[CartItem] = []

    model_config = {
        "from_attributes": True,
    }
