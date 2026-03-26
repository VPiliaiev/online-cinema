import pytest
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload, joinedload

from database import MovieModel, GenreModel, StarModel, DirectorModel, CertificationModel


@pytest.mark.asyncio
async def test_get_movies_empty_database(client):
    """
    Test that the `/movies/` endpoint returns a 404 error when the database is empty.
    """
    response = await client.get("/api/v1/theater/movies/")
    assert response.status_code == 404
    assert response.json() == {"detail": "No movies found."}


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
