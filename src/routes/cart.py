from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_jwt_auth_manager
from database import get_db, MovieModel

from database.models.cart import CartModel, CartItemModel
from exceptions import BaseSecurityError
from schemas.cart import Cart, CartItemCreate
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface

router = APIRouter()


@router.get(
    "/",
    response_model=Cart,
    summary="Get current user cart"
)
async def get_cart(
        token: str = Depends(get_token),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        db: AsyncSession = Depends(get_db)
):
    try:
        payload = jwt_manager.decode_access_token(token)
        user_id = payload.get("user_id")
    except BaseSecurityError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired or invalid")
    stmt = (
        select(CartModel)
        .where(CartModel.user_id == user_id)
        .options(selectinload(CartModel.items))
    )
    result = await db.execute(stmt)
    cart = result.scalars().first()
    if not cart:
        cart = CartModel(user_id=user_id)
        db.add(cart)
        await db.commit()
    # Re-fetch cart with eager-loaded items to avoid async lazy-load
    # during response serialization (MissingGreenlet).
    result = await db.execute(stmt)
    return result.scalars().first()


@router.post(
    "/items/",
    response_model=Cart,
    summary="Add movie to cart"
)
async def add_item(
        data: CartItemCreate,
        token: str = Depends(get_token),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        db: AsyncSession = Depends(get_db)
):
    payload = jwt_manager.decode_access_token(token)
    user_id = payload.get("user_id")

    movie = await db.get(MovieModel, data.movie_id)
    if not movie:
        raise HTTPException(404, "Movie not found")

    stmt = select(CartModel).where(CartModel.user_id == user_id).options(selectinload(CartModel.items))
    res = await db.execute(stmt)
    cart = res.scalars().first()

    if not cart:
        cart = CartModel(user_id=user_id)
        db.add(cart)
        await db.flush()

    existing_stmt = select(CartItemModel).where(
        CartItemModel.cart_id == cart.id,
        CartItemModel.movie_id == data.movie_id
    )
    existing_res = await db.execute(existing_stmt)
    if existing_res.scalars().first():
        raise HTTPException(400, "Movie already in cart")
    new_item = CartItemModel(cart_id=cart.id, movie_id=data.movie_id)
    db.add(new_item)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(500, "Database error")
    final_stmt = select(CartModel).where(CartModel.id == cart.id).options(
        selectinload(CartModel.items)
    )
    final_res = await db.execute(final_stmt)
    return final_res.scalars().first()


@router.delete(
    "/items/{item_id}/",
    response_model=Cart,
    summary="Remove specific item from cart"
)
async def remove_item(
        item_id: int,
        token: str = Depends(get_token),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        db: AsyncSession = Depends(get_db)
):
    payload = jwt_manager.decode_access_token(token)
    user_id = payload.get("user_id")
    cart_stmt = select(CartModel).where(CartModel.user_id == user_id)
    cart_res = await db.execute(cart_stmt)
    cart = cart_res.scalars().first()

    if not cart:
        raise HTTPException(404, "Cart not found")
    item_stmt = select(CartItemModel).where(
        CartItemModel.id == item_id,
        CartItemModel.cart_id == cart.id
    )
    item_res = await db.execute(item_stmt)
    item = item_res.scalars().first()
    if not item:
        raise HTTPException(404, "Item not found in your cart")
    await db.delete(item)
    await db.commit()
    final_stmt = select(CartModel).where(CartModel.id == cart.id).options(
        selectinload(CartModel.items)
    )
    final_res = await db.execute(final_stmt)
    return final_res.scalars().first()


@router.delete(
    "/",
    response_model=Cart,
    summary="Clear entire cart"
)
async def clear_cart(
        token: str = Depends(get_token),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        db: AsyncSession = Depends(get_db)
):
    payload = jwt_manager.decode_access_token(token)
    user_id = payload.get("user_id")
    stmt = select(CartModel).where(CartModel.user_id == user_id)
    res = await db.execute(stmt)
    cart = res.scalars().first()
    if cart:
        delete_stmt = delete(CartItemModel).where(CartItemModel.cart_id == cart.id)
        await db.execute(delete_stmt)
        await db.commit()
    return await get_cart(token, jwt_manager, db)
