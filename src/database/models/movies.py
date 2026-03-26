import uuid as python_uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import (
    String, Text, DECIMAL, UniqueConstraint,
    ForeignKey, Table, Column, Integer, text, CheckConstraint
)
from sqlalchemy.orm import mapped_column, Mapped, relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from database import Base

movie_genres = Table(
    "movie_genres",
    Base.metadata,
    Column("movie_id", ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True),
    Column("genre_id", ForeignKey("genres.id", ondelete="CASCADE"), primary_key=True),
)

movie_stars = Table(
    "movie_stars",
    Base.metadata,
    Column("movie_id", ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True),
    Column("star_id", ForeignKey("stars.id", ondelete="CASCADE"), primary_key=True),
)

movie_directors = Table(
    "movie_directors",
    Base.metadata,
    Column("movie_id", ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True),
    Column("director_id", ForeignKey("directors.id", ondelete="CASCADE"), primary_key=True),
)


class GenreModel(Base):
    __tablename__ = "genres"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    movies: Mapped[List["MovieModel"]] = relationship(
        secondary=movie_genres,
        back_populates="genres"
    )


class StarModel(Base):
    __tablename__ = "stars"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    movies: Mapped[List["MovieModel"]] = relationship(
        secondary=movie_stars,
        back_populates="stars"
    )


class DirectorModel(Base):
    __tablename__ = "directors"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    movies: Mapped[List["MovieModel"]] = relationship(
        secondary=movie_directors,
        back_populates="directors"
    )


class CertificationModel(Base):
    __tablename__ = "certifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    movies: Mapped[List["MovieModel"]] = relationship(
        back_populates="certification"
    )


class MovieModel(Base):
    __tablename__ = "movies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    uuid: Mapped[python_uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        default=python_uuid.uuid4,
        unique=True,
        nullable=False,
        index=True
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    time: Mapped[int] = mapped_column(Integer, nullable=False)

    votes: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0"),
        nullable=False
    )

    imdb: Mapped[Decimal] = mapped_column(DECIMAL(3, 1), nullable=False)
    meta_score: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(4, 1))
    gross: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(15, 2))

    description: Mapped[str] = mapped_column(Text, nullable=False)
    price: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)

    certification_id: Mapped[int] = mapped_column(
        ForeignKey("certifications.id"),
        nullable=False
    )

    certification: Mapped["CertificationModel"] = relationship(
        back_populates="movies"
    )

    genres: Mapped[List["GenreModel"]] = relationship(
        secondary=movie_genres,
        back_populates="movies"
    )

    stars: Mapped[List["StarModel"]] = relationship(
        secondary=movie_stars,
        back_populates="movies"
    )

    directors: Mapped[List["DirectorModel"]] = relationship(
        secondary=movie_directors,
        back_populates="movies"
    )

    ratings: Mapped[List["RatingMovieModel"]] = relationship(
        back_populates="movie"
    )

    favorites: Mapped[List["FavoriteMovieModel"]] = relationship(
        back_populates="movie"
    )

    comments: Mapped[List["CommentMovieModel"]] = relationship(
        back_populates="movie"
    )

    __table_args__ = (
        UniqueConstraint("name", "year", "time", name="unique_movie_identity"),
        CheckConstraint("imdb >= 0 AND imdb <= 10", name="imdb_range_check"),
        CheckConstraint("votes >= 0", name="votes_positive_check"),
    )

    @classmethod
    def default_order_by(cls):
        return [cls.id.desc()]


class RatingMovieModel(Base):
    __tablename__ = "ratings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id"), nullable=False)

    value: Mapped[int] = mapped_column(Integer, nullable=False)

    user = relationship("UserModel")
    movie = relationship("MovieModel", back_populates="ratings")

    __table_args__ = (
        UniqueConstraint("user_id", "movie_id"),
        CheckConstraint("value >= 1 AND value <= 10", name="rating_range_check"),
    )


class FavoriteMovieModel(Base):
    __tablename__ = "favorites"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id"), primary_key=True)

    user = relationship("UserModel")
    movie = relationship("MovieModel", back_populates="favorites")


class CommentMovieModel(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id"), nullable=False)

    content: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )

    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("comments.id"),
        nullable=True
    )

    user = relationship("UserModel")
    movie = relationship("MovieModel", back_populates="comments")

    parent: Mapped[Optional["CommentMovieModel"]] = relationship(
        "CommentMovieModel",
        remote_side=[id],
        backref="replies",
        cascade="all, delete"
    )
