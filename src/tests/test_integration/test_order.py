import pytest
from sqlalchemy import select
from database.models.accounts import UserModel, UserGroupModel, UserGroupEnum
from database.models.order import OrderModel, OrderStatusEnum


@pytest.mark.asyncio
async def test_create_order_success(client, db_session, seed_user_groups, seed_database):
    email = "fav_test@example.com"
    password = "Password123!"
    movie_id = 1
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

    await client.post(
        "/api/v1/cart/items/",
        json={"movie_id": movie_id},
        headers=headers
    )
    await client.post(
        "/api/v1/cart/items/",
        json={"movie_id": 2},
        headers=headers
    )

    create_res = await client.post("/api/v1/orders/", headers=headers)
    assert create_res.status_code == 201
    data = create_res.json()
    assert data["user_id"] == user.id
    assert data["status"] == "pending"
    assert len(data["items"]) == 2
    assert {item["movie_id"] for item in data["items"]} == {1, 2}
    assert data["total_amount"] is not None

    cart_res = await client.get("/api/v1/cart/", headers=headers)
    assert cart_res.status_code == 200
    assert cart_res.json()["items"] == []


@pytest.mark.asyncio
async def test_create_order_empty_cart(client, db_session, seed_user_groups):
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
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    response = await client.post("/api/v1/orders/", headers=headers)
    assert response.status_code == 400
    assert response.json()["detail"] == "Cart is empty"


@pytest.mark.asyncio
async def test_read_order_success(client, db_session, seed_user_groups, seed_database):
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
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    await client.post(
        "/api/v1/cart/items/",
        json={"movie_id": 1},
        headers=headers
    )
    create_res = await client.post("/api/v1/orders/", headers=headers)
    order_id = create_res.json()["id"]

    response = await client.get(f"/api/v1/orders/{order_id}/", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == order_id
    assert len(body["items"]) == 1
    assert body["items"][0]["movie_id"] == 1


@pytest.mark.asyncio
async def test_read_order_not_found(client, db_session, seed_user_groups):
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
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    response = await client.get("/api/v1/orders/99999/", headers=headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Order not found"


@pytest.mark.asyncio
async def test_read_order_other_user_forbidden(client, db_session, seed_user_groups, seed_database):
    res_group = await db_session.execute(
        select(UserGroupModel).filter_by(name=UserGroupEnum.USER)
    )
    group_id = res_group.scalars().first().id

    # Власник замовлення
    owner = UserModel.create(
        email="fav_test@example.com",
        raw_password="Password123!",
        group_id=group_id
    )
    owner.is_active = True

    # Інший користувач
    other = UserModel.create(
        email="other_test@example.com",
        raw_password="Password123!",
        group_id=group_id
    )
    other.is_active = True

    db_session.add_all([owner, other])
    await db_session.commit()

    owner_login = await client.post(
        "/api/v1/accounts/login/",
        json={"email": owner.email, "password": "Password123!"}
    )
    owner_headers = {"Authorization": f"Bearer {owner_login.json()['access_token']}"}

    await client.post(
        "/api/v1/cart/items/",
        json={"movie_id": 1},
        headers=owner_headers
    )
    create_res = await client.post("/api/v1/orders/", headers=owner_headers)
    order_id = create_res.json()["id"]

    other_login = await client.post(
        "/api/v1/accounts/login/",
        json={"email": other.email, "password": "Password123!"}
    )
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}

    response = await client.get(f"/api/v1/orders/{order_id}/", headers=other_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Order not found"


@pytest.mark.asyncio
async def test_cancel_order_success(client, db_session, seed_user_groups, seed_database):
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
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    await client.post(
        "/api/v1/cart/items/",
        json={"movie_id": 1},
        headers=headers
    )
    create_res = await client.post("/api/v1/orders/", headers=headers)
    order_id = create_res.json()["id"]

    response = await client.patch(
        f"/api/v1/orders/{order_id}/cancel/",
        headers=headers
    )
    assert response.status_code == 200
    assert response.json()["status"] == "canceled"


@pytest.mark.asyncio
async def test_cancel_order_already_canceled(client, db_session, seed_user_groups, seed_database):
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
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    await client.post(
        "/api/v1/cart/items/",
        json={"movie_id": 1},
        headers=headers
    )
    create_res = await client.post("/api/v1/orders/", headers=headers)
    order_id = create_res.json()["id"]

    await client.patch(f"/api/v1/orders/{order_id}/cancel/", headers=headers)
    response = await client.patch(
        f"/api/v1/orders/{order_id}/cancel/",
        headers=headers
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Order already canceled"


@pytest.mark.asyncio
async def test_create_order_unauthorized(client):
    response = await client.post("/api/v1/orders/")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_read_order_unauthorized(client):
    response = await client.get("/api/v1/orders/1/")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_cancel_order_unauthorized(client):
    response = await client.patch("/api/v1/orders/1/cancel/")
    assert response.status_code == 401
