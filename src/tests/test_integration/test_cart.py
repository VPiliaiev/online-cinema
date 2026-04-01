import pytest
from sqlalchemy import select
from database.models.accounts import UserModel, UserGroupModel, UserGroupEnum


@pytest.mark.asyncio
async def test_get_empty_cart_success(client, db_session, seed_user_groups):
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
    response = await client.get("/api/v1/cart/", headers=headers)
    assert response.status_code == 200
    assert response.json()["items"] == []


@pytest.mark.asyncio
async def test_add_item_to_cart_success(client, db_session, seed_user_groups, seed_database):
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
    response = await client.post(
        "/api/v1/cart/items/",
        json={"movie_id": movie_id},
        headers=headers
    )
    assert response.status_code == 200
    assert len(response.json()["items"]) == 1
    assert response.json()["items"][0]["movie_id"] == movie_id


@pytest.mark.asyncio
async def test_add_duplicate_item(client, db_session, seed_user_groups, seed_database):
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
    response = await client.post(
        "/api/v1/cart/items/",
        json={"movie_id": movie_id},
        headers=headers
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Movie already in cart"


@pytest.mark.asyncio
async def test_remove_item_success(client, db_session, seed_user_groups, seed_database):
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
    add_res = await client.post(
        "/api/v1/cart/items/",
        json={"movie_id": movie_id},
        headers=headers
    )
    item_id = add_res.json()["items"][0]["id"]
    response = await client.delete(
        f"/api/v1/cart/items/{item_id}/",
        headers=headers
    )
    assert response.status_code == 200
    assert len(response.json()["items"]) == 0


@pytest.mark.asyncio
async def test_clear_cart_success(client, db_session, seed_user_groups, seed_database):
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
    await client.post("/api/v1/cart/items/", json={"movie_id": 1}, headers=headers)
    await client.post("/api/v1/cart/items/", json={"movie_id": 2}, headers=headers)
    response = await client.delete("/api/v1/cart/", headers=headers)
    assert response.status_code == 200
    assert len(response.json()["items"]) == 0


@pytest.mark.asyncio
async def test_get_cart_unauthorized(client):
    response = await client.get("/api/v1/cart/")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_add_item_movie_not_found(client, db_session, seed_user_groups):
    email = "test@example.com"
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
    response = await client.post(
        "/api/v1/cart/items/",
        json={"movie_id": 9999},
        headers=headers
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Movie not found"
