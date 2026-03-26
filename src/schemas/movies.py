from datetime import datetime
from typing import Optional, List
from uuid import UUID
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class GenreSchema(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class StarSchema(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class DirectorSchema(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class CertificationSchema(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class MovieBaseSchema(BaseModel):
    name: str = Field(..., max_length=255)
    year: int = Field(..., ge=1888)
    time: int = Field(..., ge=1)
    imdb: Decimal = Field(..., ge=0, le=10)
    meta_score: Optional[Decimal] = Field(None, ge=0, le=100)
    gross: Optional[Decimal] = Field(None, ge=0)
    description: str
    price: Decimal = Field(..., ge=0)

    model_config = {"from_attributes": True}

    @field_validator("year")
    @classmethod
    def validate_year(cls, value):
        current_year = datetime.now().year
        if value > current_year + 5:
            raise ValueError(f"Year cannot be greater than {current_year + 5}")
        return value


class MovieDetailSchema(MovieBaseSchema):
    id: int
    uuid: UUID
    votes: int
    certification: CertificationSchema
    genres: List[GenreSchema]
    stars: List[StarSchema]
    directors: List[DirectorSchema]

    model_config = {
        "from_attributes": True,
    }


class MovieListItemSchema(BaseModel):
    id: int
    uuid: UUID
    name: str
    year: int
    imdb: Decimal
    price: Decimal
    genres: List[GenreSchema]

    model_config = {
        "from_attributes": True,
    }


class MovieListResponseSchema(BaseModel):
    movies: List[MovieListItemSchema]
    prev_page: Optional[str]
    next_page: Optional[str]
    total_pages: int
    total_items: int

    model_config = {"from_attributes": True}


class MovieCreateSchema(MovieBaseSchema):
    certification: str
    genres: List[str]
    stars: List[str]
    directors: List[str]

    model_config = {
        "from_attributes": True,
    }

    @field_validator("genres", "stars", "directors", mode="before")
    @classmethod
    def normalize_list_fields(cls, value: List[str]) -> List[str]:
        return [item.strip().title() for item in value]


class MovieUpdateSchema(BaseModel):
    name: Optional[str] = None
    year: Optional[int] = None
    time: Optional[int] = None
    imdb: Optional[Decimal] = None
    meta_score: Optional[Decimal] = None
    gross: Optional[Decimal] = None
    description: Optional[str] = None
    price: Optional[Decimal] = None
    certification_id: Optional[int] = None

    model_config = {
        "from_attributes": True,
    }
