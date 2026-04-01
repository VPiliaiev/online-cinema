from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import get_jwt_auth_manager
from database import get_db
from database.models.cart import CartModel, CartItemModel
from database.models.order import OrderModel, OrderItemModel, OrderStatusEnum
from exceptions import BaseSecurityError
from schemas.order import Order
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface

router = APIRouter()


@router.post(
    "/",
    response_model=Order,
    status_code=status.HTTP_201_CREATED,
    summary="Create order from cart",
    description="Converts the user current cart into a pending order and clears the cart",
    responses={
        400: {"description": "Cart is empty"},
        401: {"description": "Unauthorized"},
        500: {"description": "Database error"}
    }
)
async def create_order(
        token: str = Depends(get_token),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        db: AsyncSession = Depends(get_db),
):
    try:
        payload = jwt_manager.decode_access_token(token)
        user_id = payload.get("user_id")
    except BaseSecurityError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired or invalid")
    cart_stmt = (
        select(CartModel)
        .where(CartModel.user_id == user_id)
        .options(selectinload(CartModel.items).selectinload(CartItemModel.movie))
    )
    cart_res = await db.execute(cart_stmt)
    cart = cart_res.scalars().first()
    if not cart or not cart.items:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cart is empty")
    total_amount = sum(float(item.movie.price) for item in cart.items)
    new_order = OrderModel(
        user_id=user_id,
        status=OrderStatusEnum.PENDING,
        total_amount=total_amount
    )
    db.add(new_order)
    for cart_item in cart.items:
        new_order.items.append(
            OrderItemModel(
                movie_id=cart_item.movie_id,
                price_at_order=float(cart_item.movie.price)
            )
        )
    cart.items.clear()
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Database error")
    final_stmt = (
        select(OrderModel)
        .where(OrderModel.id == new_order.id)
        .options(selectinload(OrderModel.items))
    )
    final_res = await db.execute(final_stmt)
    return final_res.scalars().first()


@router.get(
    "/{order_id}/",
    response_model=Order,
    summary="Read order by id",
    description="Retrieves a specific order's details including its items. Access restricted to the owner.",
    responses={
        404: {"description": "Order not found"},
        401: {"description": "Unauthorized"}
    }
)
async def read_order(
        order_id: int,
        token: str = Depends(get_token),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        db: AsyncSession = Depends(get_db),
):
    try:
        payload = jwt_manager.decode_access_token(token)
        user_id = payload.get("user_id")
    except BaseSecurityError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired or invalid")
    stmt = (
        select(OrderModel)
        .where(OrderModel.id == order_id, OrderModel.user_id == user_id)
        .options(selectinload(OrderModel.items))
    )
    result = await db.execute(stmt)
    order = result.scalars().first()
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
    return order


@router.patch(
    "/{order_id}/cancel/",
    response_model=Order,
    summary="Cancel order",
    description="Updates order status to 'canceled'. Only allowed for 'pending' orders owned by the user.",
    responses={
        400: {"description": "Order already canceled or paid"},
        404: {"description": "Order not found"},
        401: {"description": "Unauthorized"}
    }
)
async def cancel_order(
        order_id: int,
        token: str = Depends(get_token),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        db: AsyncSession = Depends(get_db),
):
    try:
        payload = jwt_manager.decode_access_token(token)
        user_id = payload.get("user_id")
    except BaseSecurityError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired or invalid")
    stmt = (
        select(OrderModel)
        .where(OrderModel.id == order_id, OrderModel.user_id == user_id)
        .options(selectinload(OrderModel.items))
    )
    result = await db.execute(stmt)
    order = result.scalars().first()
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
    if order.status == OrderStatusEnum.CANCELED:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Order already canceled")
    if order.status == OrderStatusEnum.PAID:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Paid order cannot be canceled")
    order.status = OrderStatusEnum.CANCELED
    await db.commit()
    await db.refresh(order)
    return order
