from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from config import get_jwt_auth_manager, get_settings
from database import get_db
from database.models.order import OrderModel, OrderItemModel, OrderStatusEnum
from database.models.payment import PaymentItemModel, PaymentModel, PaymentStatusEnum
from exceptions import BaseSecurityError
from schemas.payment import PaymentCreate, StripeSessionResponse
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
import stripe

router = APIRouter(tags=["payments"])


def _get_current_user_id(
    token: str,
    jwt_manager: JWTAuthManagerInterface,
) -> int:
    try:
        payload = jwt_manager.decode_access_token(token)
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token payload")
        return int(user_id)
    except BaseSecurityError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired or invalid")


@router.post(
    "/checkout/",
    response_model=StripeSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Stripe checkout session",
    description=(
        "Creates a Stripe Checkout Session for a **pending** order owned by the current user. "
        "Before returning, it also writes a `PaymentModel` (status=`pending`) and corresponding "
        "`PaymentItemModel` rows based on the order items.\n\n"
        "JWT is required (`Authorization: Bearer <token>`)."
    ),
    responses={
        201: {"description": "Checkout session created successfully."},
        400: {"description": "Order is empty or not in `pending` state."},
        401: {"description": "Unauthorized (missing or invalid token)."},
        404: {"description": "Order not found."},
        500: {"description": "Stripe session URL is empty or payment persistence failed."},
    },
)
async def create_checkout_session(
        payment_data: PaymentCreate,
        token: str = Depends(get_token),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        db: AsyncSession = Depends(get_db),
):
    user_id = _get_current_user_id(token, jwt_manager)
    settings = get_settings()
    stripe.api_key = settings.STRIPE_SECRET_KEY
    order_stmt = (
        select(OrderModel)
        .where(OrderModel.id == payment_data.order_id, OrderModel.user_id == user_id)
        .options(selectinload(OrderModel.items).selectinload(OrderItemModel.movie))
    )
    order_res = await db.execute(order_stmt)
    order = order_res.scalars().first()
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
    if order.status != OrderStatusEnum.PENDING:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only pending orders can be paid")
    items = order.items or []
    if not items:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Order has no items")
    total_amount = float(order.total_amount) if order.total_amount is not None else float(
        sum(item.price_at_order for item in items)
    )
    payment = PaymentModel(
        user_id=user_id,
        order_id=order.id,
        amount=total_amount,
        status=PaymentStatusEnum.PENDING,
        external_payment_id=payment_data.external_payment_id,
    )
    db.add(payment)
    await db.flush()
    for order_item in items:
        db.add(
            PaymentItemModel(
                payment_id=payment.id,
                order_item_id=order_item.id,
                price_at_payment=float(order_item.price_at_order),
            )
        )
    line_items = []
    for order_item in items:
        movie_name = None
        if getattr(order_item, "movie", None):
            movie_name = getattr(order_item.movie, "name", None)
        if not movie_name:
            movie_name = f"Movie #{order_item.movie_id}"
        unit_amount_cents = int(round(float(order_item.price_at_order) * 100))
        line_items.append(
            {
                "quantity": 1,
                "price_data": {
                    "currency": "usd",
                    "unit_amount": unit_amount_cents,
                    "product_data": {"name": movie_name},
                },
            }
        )

    success_url = "http://localhost:8000/docs"
    cancel_url = "http://localhost:8000/docs"
    session = stripe.checkout.Session.create(
        mode="payment",
        payment_method_types=["card"],
        line_items=line_items,
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "payment_id": str(payment.id),
            "order_id": str(order.id),
            "user_id": str(user_id),
        },
    )
    if not session.url:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Stripe session URL is empty")
    payment.external_payment_id = session.id
    await db.commit()
    return StripeSessionResponse(
        order_id=order.id,
        checkout_url=session.url,
        payment_id=payment.id,
    )
