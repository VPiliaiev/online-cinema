from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from database import get_db, MovieModel, CertificationModel, StarModel, DirectorModel
from database import (
    GenreModel
)
from schemas import (
    MovieListResponseSchema,
    MovieListItemSchema,
    MovieDetailSchema
)
from schemas.movies import MovieCreateSchema, MovieUpdateSchema

router = APIRouter()


@router.get(
    "/movies/",
    response_model=MovieListResponseSchema,
    summary="Get a paginated and filtered list of movies",
    description=(
            "<h3>Retrieve movies with advanced filtering, searching, and sorting.</h3>"
            "<ul>"
            "<li><b>Search:</b> Filter by title or description using partial matches.</li>"
            "<li><b>Crew:</b> Search movies by specific actor or director names.</li>"
            "<li><b>Ranges:</b> Filter movies by release year range and minimum IMDb rating.</li>"
            "<li><b>Pagination:</b> Control result set using page and per_page parameters.</li>"
            "<li><b>Sorting:</b> Sort by ID, Name, Year, IMDb score, or Price.</li>"
            "</ul>"
    ),
    responses={
        200: {"description": "Successfully retrieved the movie list."},
        404: {
            "description": "No movies found matching the criteria.",
            "content": {"application/json": {"example": {"detail": "No movies found"}}}
        }
    }
)
async def get_movie_list(
        page: int = Query(1, ge=1, description="The page number to retrieve"),
        per_page: int = Query(10, ge=1, le=20, description="Items per page"),
        search: Optional[str] = Query(None, description="Search term for title or description"),
        actor: Optional[str] = Query(None, description="Filter by actor name"),
        director: Optional[str] = Query(None, description="Filter by director name"),
        year_from: Optional[int] = Query(None, ge=1888, description="Release year from"),
        year_to: Optional[int] = Query(None, ge=1888, description="Release year to"),
        imdb_min: Optional[float] = Query(None, ge=0, le=10, description="Minimum IMDb rating"),
        sort_by: str = Query("id", enum=["id", "name", "year", "imdb", "price"]),
        order: str = Query("desc", enum=["asc", "desc"]),
        db: AsyncSession = Depends(get_db),
) -> MovieListResponseSchema:
    stmt = select(MovieModel).options(selectinload(MovieModel.genres))

    if search:
        stmt = stmt.where(
            or_(
                MovieModel.name.ilike(f"%{search}%"),
                MovieModel.description.ilike(f"%{search}%")
            )
        )

    if year_from:
        stmt = stmt.where(MovieModel.year >= year_from)
    if year_to:
        stmt = stmt.where(MovieModel.year <= year_to)
    if imdb_min:
        stmt = stmt.where(MovieModel.imdb >= imdb_min)
    if actor:
        stmt = stmt.where(MovieModel.stars.any(StarModel.name.ilike(f"%{actor}%")))
    if director:
        stmt = stmt.where(MovieModel.directors.any(DirectorModel.name.ilike(f"%{director}%")))

    SORT_FIELDS = {
        "id": MovieModel.id,
        "name": MovieModel.name,
        "year": MovieModel.year,
        "imdb": MovieModel.imdb,
        "price": MovieModel.price,
    }
    column = SORT_FIELDS.get(sort_by, MovieModel.id)
    stmt = stmt.order_by(column.asc() if order == "asc" else column.desc())
    count_stmt = select(func.count()).select_from(stmt.subquery())
    count_result = await db.execute(count_stmt)
    total_items = count_result.scalar() or 0
    if total_items == 0:
        raise HTTPException(status_code=404, detail="No movies found.")
    offset = (page - 1) * per_page
    stmt = stmt.offset(offset).limit(per_page)
    result = await db.execute(stmt)
    movies = result.scalars().all()
    if not movies:
        raise HTTPException(status_code=404, detail="No movies found for this page")
    total_pages = (total_items + per_page - 1) // per_page
    return MovieListResponseSchema(
        movies=[MovieListItemSchema.model_validate(m) for m in movies],
        prev_page=f"/movies/?page={page - 1}" if page > 1 else None,
        next_page=f"/movies/?page={page + 1}" if page < total_pages else None,
        total_pages=total_pages,
        total_items=total_items,
    )


async def get_or_create(db: AsyncSession, model, **kwargs):
    stmt = select(model).filter_by(**kwargs)
    result = await db.execute(stmt)
    instance = result.scalars().first()
    if instance:
        return instance
    else:
        instance = model(**kwargs)
        db.add(instance)
        await db.flush()
        return instance


@router.post(
    "/movies/",
    response_model=MovieDetailSchema,
    status_code=201,
    summary="Add a new movie",
    description=(
            "<h3>Add a new movie and link related entities.</h3>"
            "<p>This endpoint automatically handles the creation or linking of <b>genres</b>, "
            "<b>stars</b>, <b>directors</b>, and <b>certifications</b> based on the provided names.</p>"
    ),
    responses={
        409: {"description": "Conflict: Movie already exists."},
        400: {"description": "Invalid input data."}
    }
)
async def create_movie(
        movie_data: MovieCreateSchema,
        db: AsyncSession = Depends(get_db)
) -> MovieDetailSchema:
    """
    Create a new movie record.

    :param movie_data: Pydantic schema containing movie attributes and related entity names.
    :param db: Async database session.
    :return: Detailed movie information after creation.
    """
    existing_stmt = select(MovieModel).where(
        MovieModel.name == movie_data.name,
        MovieModel.year == movie_data.year,
        MovieModel.time == movie_data.time
    )
    existing_result = await db.execute(existing_stmt)
    if existing_result.scalars().first():
        raise HTTPException(
            status_code=409,
            detail=f"Movie '{movie_data.name}' ({movie_data.year}) already exists."
        )

    try:
        certification = await get_or_create(db, CertificationModel, name=movie_data.certification)
        genres = [await get_or_create(db, GenreModel, name=g) for g in movie_data.genres]
        stars = [await get_or_create(db, StarModel, name=s) for s in movie_data.stars]
        directors = [await get_or_create(db, DirectorModel, name=d) for d in movie_data.directors]

        new_movie = MovieModel(
            name=movie_data.name,
            year=movie_data.year,
            time=movie_data.time,
            imdb=movie_data.imdb,
            meta_score=movie_data.meta_score,
            gross=movie_data.gross,
            description=movie_data.description,
            price=movie_data.price,
            certification=certification,
            genres=genres,
            stars=stars,
            directors=directors
        )

        db.add(new_movie)
        await db.commit()
        await db.refresh(new_movie, ["certification", "genres", "stars", "directors"])
        return MovieDetailSchema.model_validate(new_movie)

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"Invalid input data: {str(e)}")


@router.get(
    "/movies/{movie_id}/",
    response_model=MovieDetailSchema,
    summary="Get movie details by ID",
    description="<h3>Fetch all information for a specific movie.</h3><p>Includes nested objects for genres, crew, and certification.</p>",
    responses={404: {"description": "Movie not found."}}
)
async def get_movie_by_id(
        movie_id: int,
        db: AsyncSession = Depends(get_db),
) -> MovieDetailSchema:
    """
    Retrieve details of a single movie.

    :param movie_id: Database ID of the movie.
    """
    stmt = (
        select(MovieModel)
        .options(
            joinedload(MovieModel.certification),
            selectinload(MovieModel.genres),
            selectinload(MovieModel.stars),
            selectinload(MovieModel.directors)
        )
        .where(MovieModel.id == movie_id)
    )

    result = await db.execute(stmt)
    movie = result.scalars().unique().first()

    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found.")

    return MovieDetailSchema.model_validate(movie)


@router.delete(
    "/movies/{movie_id}/",
    summary="Delete a movie by ID",
    description="<h3>Permanently remove a movie from the database.</h3>",
    status_code=204,
    responses={
        204: {"description": "Movie deleted successfully."},
        404: {"description": "Movie not found."}
    }
)
async def delete_movie(
        movie_id: int,
        db: AsyncSession = Depends(get_db),
):
    """
    Remove a movie record by ID.
    """
    stmt = select(MovieModel).where(MovieModel.id == movie_id)
    result = await db.execute(stmt)
    movie = result.scalars().first()

    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found.")

    await db.delete(movie)
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")
    return None


@router.patch(
    "/movies/{movie_id}/",
    response_model=MovieDetailSchema,
    summary="Update a movie by ID",
    description="<h3>Update specific fields of an existing movie.</h3><p>Only provided fields will be modified.</p>",
    responses={
        200: {"description": "Movie updated successfully."},
        404: {"description": "Movie not found."}
    }
)
async def update_movie(
        movie_id: int,
        movie_data: MovieUpdateSchema,
        db: AsyncSession = Depends(get_db),
):
    """
    Partially update a movie record.

    :param movie_id: ID of the movie to update.
    :param movie_data: Schema containing fields to update.
    """
    stmt = (
        select(MovieModel)
        .options(
            selectinload(MovieModel.genres),
            selectinload(MovieModel.stars),
            selectinload(MovieModel.directors),
            joinedload(MovieModel.certification)
        )
        .where(MovieModel.id == movie_id)
    )
    result = await db.execute(stmt)
    movie = result.scalars().unique().first()

    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found.")

    update_data = movie_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(movie, field, value)

    try:
        await db.commit()
        await db.refresh(movie)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Constraints violation on update.")
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    return movie
