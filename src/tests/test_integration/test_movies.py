import pytest
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload, joinedload

from database import MovieModel, GenreModel, StarModel, DirectorModel, CertificationModel, UserGroupModel, \
    UserGroupEnum, UserModel
from database.models.movies import MovieReactionModel


@pytest.mark.asyncio
async def test_get_movies_empty_database(client):
    from database import reset_database
    await reset_database()

    response = await client.get("/api/v1/theater/movies/")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_movies_default_parameters(client, seed_database):
    """
    Test the `/movies/` endpoint with default pagination parameters (page=1, per_page=10).
    """
    response = await client.get("/api/v1/theater/movies/")
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data["movies"]) == 10
    assert response_data["total_pages"] > 0
    assert response_data["total_items"] > 0
    assert response_data["prev_page"] is None


@pytest.mark.asyncio
async def test_get_movies_with_custom_parameters(client, seed_database):
    """
    Test the `/movies/` endpoint with custom pagination (page=2, per_page=5).
    """
    page = 2
    per_page = 5
    response = await client.get(f"/api/v1/theater/movies/?page={page}&per_page={per_page}")
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data["movies"]) == per_page
    assert f"page={page - 1}" in response_data["prev_page"]


@pytest.mark.asyncio
@pytest.mark.parametrize("page, per_page, expected_detail", [
    (0, 10, "Input should be greater than or equal to 1"),
    (1, 0, "Input should be greater than or equal to 1"),
    (1, 21, "Input should be less than or equal to 20"),
])
async def test_invalid_page_and_per_page(client, page, per_page, expected_detail):
    """
    Test the `/movies/` endpoint with invalid validation parameters for Pydantic.
    """
    response = await client.get(f"/api/v1/theater/movies/?page={page}&per_page={per_page}")
    assert response.status_code == 422
    response_data = response.json()
    assert any(expected_detail in error["msg"] for error in response_data["detail"])


@pytest.mark.asyncio
async def test_movies_sorted_by_id_desc(client, db_session, seed_database):
    """
    Test that movies are returned sorted by `id` in descending order by default.
    """
    response = await client.get("/api/v1/theater/movies/?page=1&per_page=10")
    assert response.status_code == 200
    response_data = response.json()
    stmt = select(MovieModel).order_by(MovieModel.id.desc()).limit(10)
    result = await db_session.execute(stmt)
    expected_movies = result.scalars().all()
    expected_ids = [m.id for m in expected_movies]
    returned_ids = [m["id"] for m in response_data["movies"]]
    assert returned_ids == expected_ids


@pytest.mark.asyncio
async def test_movies_fields_match_schema(client, db_session, seed_database):
    """
    Test that the movie list contains new fields: year, time, imdb, price.
    """
    response = await client.get("/api/v1/theater/movies/?page=1&per_page=10")
    assert response.status_code == 200
    response_data = response.json()
    expected_fields = {"id", "name", "year", "imdb", "price", "genres"}
    for movie in response_data["movies"]:
        assert expected_fields.issubset(set(movie.keys()))


@pytest.mark.asyncio
async def test_get_movie_by_id_not_found(client):
    movie_id = 99999
    response = await client.get(f"/api/v1/theater/movies/{movie_id}/")
    assert response.status_code == 404
    assert response.json()["detail"] == "Movie not found."


@pytest.mark.asyncio
async def test_get_movie_by_id_full_data(client, db_session, seed_database):
    """
    Test retrieving detailed movie info including certification, stars, and directors.
    """
    stmt = (
        select(MovieModel)
        .options(
            joinedload(MovieModel.certification),
            selectinload(MovieModel.genres),
            selectinload(MovieModel.stars),
            selectinload(MovieModel.directors)
        )
        .limit(1)
    )
    result = await db_session.execute(stmt)
    movie = result.scalars().unique().first()
    response = await client.get(f"/api/v1/theater/movies/{movie.id}/")
    assert response.status_code == 200
    data = response.json()
    assert data["certification"]["name"] == movie.certification.name
    assert "stars" in data and "directors" in data
    assert len(data["stars"]) == len(movie.stars)


@pytest.mark.asyncio
async def test_create_movie_with_nested_entities(client, db_session):
    """
    Test successful creation of a movie and automated creation of related models (get_or_create logic).
    """
    movie_data = {
        "name": "Interstellar 2",
        "year": 2026,
        "time": 160,
        "imdb": 9.0,
        "meta_score": 85,
        "gross": 500000000,
        "description": "Space exploration.",
        "price": 20.0,
        "certification": "PG-13",
        "genres": ["Sci-Fi", "Drama"],
        "stars": ["Matthew McConaughey"],
        "directors": ["Christopher Nolan"]
    }
    response = await client.post("/api/v1/theater/movies/", json=movie_data)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Interstellar 2"
    assert data["certification"]["name"] == "PG-13"


@pytest.mark.asyncio
async def test_create_movie_duplicate_conflict(client, db_session, seed_database):
    """
    Test that creating a movie with same name, year, and time returns a 409 error.
    """
    stmt = select(MovieModel).limit(1)
    result = await db_session.execute(stmt)
    existing = result.scalars().first()
    movie_data = {
        "name": existing.name,
        "year": existing.year,
        "time": existing.time,
        "imdb": 1.0, "meta_score": 10, "gross": 0, "description": "d",
        "price": 1.0, "certification": "R", "genres": [], "stars": [], "directors": []
    }
    response = await client.post("/api/v1/theater/movies/", json=movie_data)
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_delete_movie_success(client, db_session, seed_database):
    """
    Test successful deletion of a movie and verify it's gone from the DB.
    """
    stmt = select(MovieModel).limit(1)
    result = await db_session.execute(stmt)
    movie = result.scalars().first()
    response = await client.delete(f"/api/v1/theater/movies/{movie.id}/")
    assert response.status_code == 204
    stmt_check = select(MovieModel).where(MovieModel.id == movie.id)
    res_check = await db_session.execute(stmt_check)
    assert res_check.scalars().first() is None


@pytest.mark.asyncio
async def test_update_movie_partial(client, db_session, seed_database):
    """
    Test the PATCH endpoint for updating only specific fields.
    """
    stmt = select(MovieModel).limit(1)
    result = await db_session.execute(stmt)
    movie = result.scalars().first()
    update_data = {"name": "Updated Title", "price": 12.99}
    response = await client.patch(f"/api/v1/theater/movies/{movie.id}/", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Title"
    assert float(data["price"]) == 12.99


@pytest.mark.asyncio
async def test_update_movie_duplicate_conflict(client, db_session, seed_database):
    """
    Test that updating a movie's name/year/time to match another existing movie
    results in a validation or integrity error (depending on implementation).
    """
    stmt = select(MovieModel).limit(2)
    result = await db_session.execute(stmt)
    movies = result.scalars().all()
    movie_to_update = movies[0]
    target_data = movies[1]

    update_payload = {
        "name": target_data.name,
        "year": target_data.year,
        "time": target_data.time
    }

    response = await client.patch(f"/api/v1/theater/movies/{movie_to_update.id}/", json=update_payload)

    assert response.status_code in [400, 409]
    assert "constraints" in response.json()["detail"].lower() or "already exists" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_update_movie_invalid_data_types(client, seed_database):
    """
    Test that sending incorrect data types (e.g., string for price)
    to the PATCH endpoint returns a 422 Unprocessable Entity.
    """
    stmt = select(MovieModel.id).limit(1)
    movie_id = 1

    invalid_payload = {
        "price": "not-a-number",
        "year": "two thousand twenty four"
    }

    response = await client.patch(f"/api/v1/theater/movies/{movie_id}/", json=invalid_payload)
    assert response.status_code == 422
    errors = response.json()["detail"]
    assert any("price" in err["loc"] for err in errors)


@pytest.mark.asyncio
async def test_delete_movie_already_deleted(client, db_session, seed_database):
    """
    Test that attempting to delete the same movie twice returns 404 on the second attempt.
    """
    stmt = select(MovieModel.id).limit(1)
    result = await db_session.execute(stmt)
    movie_id = result.scalar()

    first_res = await client.delete(f"/api/v1/theater/movies/{movie_id}/")
    assert first_res.status_code == 204

    second_res = await client.delete(f"/api/v1/theater/movies/{movie_id}/")
    assert second_res.status_code == 404
    assert "not found" in second_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_movie_invalid_score_range(client):
    """
    Test that IMDb or Meta Score values outside reasonable limits (if defined in schema)
    are rejected.
    """
    movie_data = {
        "name": "Impossible Rating",
        "year": 2024,
        "time": 100,
        "imdb": 15.5,
        "certification": "G",
        "genres": [], "stars": [], "directors": []
    }
    response = await client.post("/api/v1/theater/movies/", json=movie_data)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_search_by_title(client, seed_database):
    """Test searching for a movie by title."""
    search_term = "Movie 01"
    response = await client.get(f"/api/v1/theater/movies/?search={search_term}")

    assert response.status_code == 200
    data = response.json()
    assert len(data["movies"]) >= 1
    assert search_term in data["movies"][0]["name"]


@pytest.mark.asyncio
async def test_filter_by_year_range(client, seed_database):
    """Test filtering movies within a specific year range."""
    year_from = 2021
    year_to = 2022
    response = await client.get(f"/api/v1/theater/movies/?year_from={year_from}&year_to={year_to}")

    assert response.status_code == 200
    data = response.json()
    for movie in data["movies"]:
        assert year_from <= movie["year"] <= year_to


@pytest.mark.asyncio
async def test_filter_by_actor(client, seed_database):
    """Test filtering movies by actor name."""
    actor_name = "Test Actor"
    response = await client.get(f"/api/v1/theater/movies/?actor={actor_name}")

    assert response.status_code == 200
    data = response.json()
    assert len(data["movies"]) > 0


@pytest.mark.asyncio
async def test_sorting_by_price_desc(client, seed_database):
    """Test sorting movies by price in descending order."""
    response = await client.get("/api/v1/theater/movies/?sort_by=price&order=desc")

    assert response.status_code == 200
    movies = response.json()["movies"]
    prices = [m["price"] for m in movies]
    assert prices == sorted(prices, reverse=True)


@pytest.mark.asyncio
async def test_search_no_results(client, seed_database):
    """Test search with a term that matches nothing (expect 404)."""
    response = await client.get("/api/v1/theater/movies/?search=NonExistentMovie")

    assert response.status_code == 404
    assert response.json()["detail"] == "No movies found."


@pytest.mark.asyncio
async def test_filter_by_imdb_rating(client, seed_database):
    """Test filtering movies by minimum IMDb score."""
    imdb_min = 8.0
    response = await client.get(f"/api/v1/theater/movies/?imdb_min={imdb_min}")

    assert response.status_code == 200
    movies = response.json()["movies"]
    for movie in movies:
        assert float(movie["imdb"]) >= imdb_min


@pytest.mark.asyncio
async def test_react_to_movie_add_like_success(client, db_session, seed_user_groups, seed_database):
    """
    Test successful addition of a like to a movie
    1. Create and activate a user
    2. Login to get access token
    3. Post a like reaction
    4. Verify DB state and response data
    """
    email = "liker@example.com"
    password = "Password123!"

    res_group = await db_session.execute(select(UserGroupModel).filter_by(name=UserGroupEnum.USER))
    user_group = res_group.scalars().first()
    user = UserModel.create(email=email, raw_password=password, group_id=user_group.id)
    user.is_active = True
    db_session.add(user)
    await db_session.commit()

    login_res = await client.post("/api/v1/accounts/login/", json={"email": email, "password": password})
    token = login_res.json()["access_token"]

    movie_id = 1
    response = await client.post(
        f"/api/v1/theater/movies/{movie_id}/react/",
        json={"is_like": True},
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["likes_count"] == 1
    assert data["user_reaction"] is True

    stmt = select(MovieReactionModel).where(
        MovieReactionModel.user_id == user.id,
        MovieReactionModel.movie_id == movie_id
    )
    result = await db_session.execute(stmt)
    reaction_record = result.scalars().first()
    assert reaction_record is not None
    assert reaction_record.is_like is True


@pytest.mark.asyncio
async def test_react_to_movie_toggle_off(client, db_session, seed_user_groups, seed_database):
    """
    Test that sending the same reaction twice removes it.
    """
    email = "toggler@example.com"
    password = "Password123!"
    movie_id = 1
    res_group = await db_session.execute(select(UserGroupModel).filter_by(name=UserGroupEnum.USER))
    user = UserModel.create(email=email, raw_password=password, group_id=res_group.scalars().first().id)
    user.is_active = True
    db_session.add(user)
    await db_session.commit()
    login_res = await client.post("/api/v1/accounts/login/", json={"email": email, "password": password})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    await client.post(f"/api/v1/theater/movies/{movie_id}/react/", json={"is_like": True}, headers=headers)
    response = await client.post(f"/api/v1/theater/movies/{movie_id}/react/", json={"is_like": True}, headers=headers)
    assert response.status_code == 200
    assert response.json()["likes_count"] == 0
    assert response.json()["user_reaction"] is None
    stmt = select(MovieReactionModel).where(MovieReactionModel.user_id == user.id)
    result = await db_session.execute(stmt)
    assert result.scalars().first() is None


@pytest.mark.asyncio
async def test_react_to_movie_change_type(client, db_session, seed_user_groups, seed_database):
    """
    Test changing a reaction from like to dislike.
    """
    email = "changer@example.com"
    password = "Password123!"
    movie_id = 1
    res_group = await db_session.execute(select(UserGroupModel).filter_by(name=UserGroupEnum.USER))
    user = UserModel.create(email=email, raw_password=password, group_id=res_group.scalars().first().id)
    user.is_active = True
    db_session.add(user)
    await db_session.commit()
    login_res = await client.post("/api/v1/accounts/login/", json={"email": email, "password": password})
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}
    await client.post(f"/api/v1/theater/movies/{movie_id}/react/", json={"is_like": True}, headers=headers)
    response = await client.post(f"/api/v1/theater/movies/{movie_id}/react/", json={"is_like": False}, headers=headers)
    assert response.status_code == 200
    assert response.json()["likes_count"] == 0
    assert response.json()["dislikes_count"] == 1
    assert response.json()["user_reaction"] is False


@pytest.mark.asyncio
async def test_react_to_movie_not_found(client, db_session, seed_user_groups):
    """
    Test reaction to a non-existent movie ID.
    """
    email = "error_test@example.com"
    password = "Password123!"
    res_group = await db_session.execute(select(UserGroupModel).filter_by(name=UserGroupEnum.USER))
    user = UserModel.create(email=email, raw_password=password, group_id=res_group.scalars().first().id)
    user.is_active = True
    db_session.add(user)
    await db_session.commit()
    login_res = await client.post("/api/v1/accounts/login/", json={"email": email, "password": password})
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}
    response = await client.post("/api/v1/theater/movies/9999/react/", json={"is_like": True}, headers=headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Movie not found."


@pytest.mark.asyncio
async def test_create_comment_and_reply_flow(client, db_session, seed_user_groups, seed_database):
    """
    Test the full flow of creating a main comment and then replying to it
    """
    email = "commenter@example.com"
    password = "Password123!"
    movie_id = 1
    res_group = await db_session.execute(select(UserGroupModel).filter_by(name=UserGroupEnum.USER))
    user = UserModel.create(email=email, raw_password=password, group_id=res_group.scalars().first().id)
    user.is_active = True
    db_session.add(user)
    await db_session.commit()
    login_res = await client.post("/api/v1/accounts/login/", json={"email": email, "password": password})
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}
    main_payload = {"content": "first comment", "parent_id": None}
    main_res = await client.post(f"/api/v1/theater/movies/{movie_id}/comments/", json=main_payload, headers=headers)
    assert main_res.status_code == 201
    parent_id = main_res.json()["id"]
    reply_payload = {"content": "Reply comment", "parent_id": parent_id}
    reply_res = await client.post(f"/api/v1/theater/movies/{movie_id}/comments/", json=reply_payload, headers=headers)
    assert reply_res.status_code == 201
    assert reply_res.json()["parent_id"] == parent_id
    get_res = await client.get(f"/api/v1/theater/movies/{movie_id}/comments/")
    assert get_res.status_code == 200
    data = get_res.json()
    root_comment = next((c for c in data if c["id"] == parent_id), None)
    assert root_comment is not None
    assert len(root_comment["replies"]) == 1
    assert root_comment["replies"][0]["content"] == "Reply comment"
    assert root_comment["replies"][0]["user"]["email"] == email


@pytest.mark.asyncio
async def test_create_comment_unauthorized(client, seed_database):
    """
    Test that unauthorized users cannot post comments.
    """
    movie_id = 1
    response = await client.post(
        f"/api/v1/theater/movies/{movie_id}/comments/",
        json={"content": "Should fail", "parent_id": None}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_comments_empty_movie(client, seed_database):
    """
    Test getting comments for a movie that has no comments.
    """
    response = await client.get("/api/v1/theater/movies/999/comments/")
    assert response.status_code == 200
    assert response.json() == []