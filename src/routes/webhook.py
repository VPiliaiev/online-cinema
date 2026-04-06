from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import get_settings
from database import get_db
from database.models.order import OrderModel, OrderStatusEnum
from database.models.payment import PaymentModel, PaymentStatusEnum
import stripe

router = APIRouter()


@router.post(
    "/webhook/",
    status_code=status.HTTP_200_OK,
    summary="Stripe webhook endpoint",
)
async def stripe_webhook(
        request: Request,
        db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature")

    if not sig_header:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Missing Stripe-Signature header")

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=settings.STRIPE_WEBHOOK_SECRET,
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid Stripe signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        metadata = session.get("metadata") or {}
        payment_id = metadata.get("payment_id")
        external_payment_id = session.get("id")

        payment = None
        if payment_id:
            payment_stmt = (
                select(PaymentModel)
                .where(PaymentModel.id == int(payment_id))
                .options(selectinload(PaymentModel.order))
            )
            res = await db.execute(payment_stmt)
            payment = res.scalars().first()

        if not payment and external_payment_id:
            payment_stmt = (
                select(PaymentModel)
                .where(PaymentModel.external_payment_id == external_payment_id)
                .options(selectinload(PaymentModel.order))
            )
            res = await db.execute(payment_stmt)
            payment = res.scalars().first()

        if payment and payment.status != PaymentStatusEnum.SUCCESSFUL:
            payment.status = PaymentStatusEnum.SUCCESSFUL
            if payment.order:
                payment.order.status = OrderStatusEnum.PAID
            await db.commit()

    return JSONResponse({"ok": True})
