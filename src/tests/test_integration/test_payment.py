import pytest
from sqlalchemy import select
from types import SimpleNamespace

from database.models.accounts import UserModel, UserGroupModel, UserGroupEnum
from database.models.order import OrderModel, OrderStatusEnum
from database.models.payment import PaymentModel, PaymentStatusEnum


async def test_login_user_with_pending_order(client, db_session, seed_user_groups, seed_database):
    email = "fav_test@example.com"
    password = "Password123!"
    res_group = await db_session.execute(
        select(UserGroupModel).filter_by(name=UserGroupEnum.USER)
    )
    user = UserModel.create(
        email=email,
        raw_password=password,
        group_id=res_group.scalars().first().id
    )
    user.is_active = True
    db_session.add(user)
    await db_session.commit()
    login_res = await client.post(
        "/api/v1/accounts/login/",
        json={"email": email, "password": password}
    )
    assert login_res.status_code == 201
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}
    await client.post(
        "/api/v1/cart/items/",
        json={"movie_id": 1},
        headers=headers
    )
    order_res = await client.post("/api/v1/orders/", headers=headers)
    assert order_res.status_code == 201
    order_data = order_res.json()
    return headers, order_data["id"], user.id, float(order_data["total_amount"])


@pytest.mark.asyncio
async def test_checkout_creates_payment_and_returns_checkout_url(
        monkeypatch, client, db_session, seed_user_groups, seed_database
):
    def fake_session_create(**kwargs):
        return SimpleNamespace(id="cs_test_fake_session_123", url="https://checkout.stripe.com/test")

    monkeypatch.setattr(
        "routes.payment.stripe.checkout.Session.create",
        fake_session_create,
    )
    headers, order_id, _user_id, total = await test_login_user_with_pending_order(
        client, db_session, seed_user_groups, seed_database
    )
    res = await client.post(
        "/api/v1/payments/checkout/",
        json={"order_id": order_id, "amount": total},
        headers=headers,
    )
    assert res.status_code == 201
    body = res.json()
    assert body["order_id"] == order_id
    assert body["checkout_url"] == "https://checkout.stripe.com/test"
    assert "payment_id" in body
    pay_stmt = select(PaymentModel).where(PaymentModel.id == body["payment_id"])
    pay_row = (await db_session.execute(pay_stmt)).scalars().first()
    assert pay_row is not None
    assert pay_row.status == PaymentStatusEnum.PENDING
    assert pay_row.external_payment_id == "cs_test_fake_session_123"


@pytest.mark.asyncio
async def test_checkout_order_not_found(
        monkeypatch, client, db_session, seed_user_groups, seed_database
):
    def fake_session_create(**kwargs):
        return SimpleNamespace(id="cs_x", url="https://x")

    monkeypatch.setattr(
        "routes.payment.stripe.checkout.Session.create",
        fake_session_create,
    )
    email = "pay_nf@example.com"
    password = "Password123!"
    res_group = await db_session.execute(
        select(UserGroupModel).filter_by(name=UserGroupEnum.USER)
    )
    user = UserModel.create(
        email=email,
        raw_password=password,
        group_id=res_group.scalars().first().id
    )
    user.is_active = True
    db_session.add(user)
    await db_session.commit()
    login_res = await client.post(
        "/api/v1/accounts/login/",
        json={"email": email, "password": password}
    )
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}
    res = await client.post(
        "/api/v1/payments/checkout/",
        json={"order_id": 99999, "amount": 1.0},
        headers=headers,
    )
    assert res.status_code == 404
    assert res.json()["detail"] == "Order not found"


@pytest.mark.asyncio
async def test_checkout_only_pending_orders(
        monkeypatch, client, db_session, seed_user_groups, seed_database
):
    def fake_session_create(**kwargs):
        return SimpleNamespace(id="cs_x", url="https://x")

    monkeypatch.setattr(
        "routes.payment.stripe.checkout.Session.create",
        fake_session_create,
    )
    headers, order_id, _uid, total = await test_login_user_with_pending_order(
        client, db_session, seed_user_groups, seed_database
    )
    order_row = await db_session.get(OrderModel, order_id)
    order_row.status = OrderStatusEnum.CANCELED
    await db_session.commit()
    res = await client.post(
        "/api/v1/payments/checkout/",
        json={"order_id": order_id, "amount": total},
        headers=headers,
    )
    assert res.status_code == 400
    assert res.json()["detail"] == "Only pending orders can be paid"


@pytest.mark.asyncio
async def test_checkout_unauthorized(client):
    res = await client.post(
        "/api/v1/payments/checkout/",
        json={"order_id": 1, "amount": 10.0},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_webhook_checkout_completed_updates_payment_and_order(
        monkeypatch, client, db_session, seed_user_groups, seed_database
):
    def fake_session_create(**kwargs):
        return SimpleNamespace(id="cs_webhook_test", url="https://checkout.stripe.com/w")

    monkeypatch.setattr(
        "routes.payment.stripe.checkout.Session.create",
        fake_session_create,
    )
    headers, order_id, _user_id, total = await test_login_user_with_pending_order(
        client, db_session, seed_user_groups, seed_database
    )
    checkout_res = await client.post(
        "/api/v1/payments/checkout/",
        json={"order_id": order_id, "amount": total},
        headers=headers,
    )
    assert checkout_res.status_code == 201
    payment_id = checkout_res.json()["payment_id"]

    def fake_construct_event(payload, sig_header, secret):
        return {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_webhook_test",
                    "metadata": {"payment_id": str(payment_id)},
                }
            },
        }

    monkeypatch.setattr(
        "routes.webhook.stripe.Webhook.construct_event",
        fake_construct_event,
    )
    wh_res = await client.post(
        "/api/v1/payments/webhook/",
        content=b"{}",
        headers={"Stripe-Signature": "t=1,v1=fake"},
    )
    assert wh_res.status_code == 200
    assert wh_res.json() == {"ok": True}

    await db_session.refresh(await db_session.get(PaymentModel, payment_id))
    pay = await db_session.get(PaymentModel, payment_id)
    assert pay.status == PaymentStatusEnum.SUCCESSFUL
    ord_row = await db_session.get(OrderModel, order_id)
    assert ord_row.status == OrderStatusEnum.PAID


@pytest.mark.asyncio
async def test_webhook_missing_signature(client):
    res = await client.post("/api/v1/payments/webhook/", content=b"{}")
    assert res.status_code == 400
    assert res.json()["detail"] == "Missing Stripe-Signature header"



