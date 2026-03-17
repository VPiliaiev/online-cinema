from datetime import date
from typing import Annotated, Optional

from fastapi import UploadFile, Form, File, HTTPException
from pydantic import BaseModel, field_validator, HttpUrl, StringConstraints

from database.models.accounts import GenderEnum
from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)


class ProfileRequestSchema(BaseModel):
    first_name: str
    last_name: str
    gender: GenderEnum
    date_of_birth: date
    info: str
    avatar: UploadFile

    @classmethod
    def as_form(
            cls,
            first_name: str = Form(...),
            last_name: str = Form(...),
            gender: str = Form(...),
            date_of_birth: date = Form(...),
            info: str = Form(...),
            avatar: UploadFile = File(...)
    ) -> "ProfileRequestSchema":
        return cls(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=date_of_birth,
            info=info,
            avatar=avatar
        )

    @field_validator("first_name", "last_name")
    @classmethod
    def check_names(cls, v: str, info) -> str:
        try:
            validate_name(v)
            return v.lower()
        except ValueError as e:
            raise HTTPException(
                status_code=422,
                detail=[{"type": "value_error", "loc": ["body", info.field_name], "msg": str(e), "input": v}]
            )

    @field_validator("gender", mode='before')
    @classmethod
    def validate_gender(cls, gender: str) -> str:
        try:
            validate_gender(gender)
            return gender
        except ValueError as e:
            raise HTTPException(
                status_code=422,
                detail=[{
                    "type": "value_error",
                    "loc": ["gender"],
                    "msg": str(e),
                    "input": gender
                }]
            )
    @field_validator("date_of_birth")
    @classmethod
    def check_birth_date(cls, v: date) -> date:
        try:
            validate_birth_date(v)
            return v
        except ValueError as e:
            raise HTTPException(
                status_code=422,
                detail=[{"type": "value_error", "loc": ["body", "date_of_birth"], "msg": str(e), "input": str(v)}]
            )

    @field_validator("avatar", mode='after')
    @classmethod
    def check_avatar(cls, v: UploadFile) -> UploadFile:
        try:
            v.file.seek(0)
            validate_image(v)
            v.file.seek(0)
            return v
        except ValueError as e:
            raise HTTPException(
                status_code=422,
                detail=[{
                    "type": "value_error",
                    "loc": ["avatar"],
                    "msg": str(e),
                    "input": v.filename
                }]
            )

    @field_validator("info")
    @classmethod
    def validate_info(cls, info: str) -> str:
        cleaned_info = info.strip()
        if not cleaned_info:
            raise HTTPException(
                status_code=422,
                detail=[{
                    "type": "value_error",
                    "loc": ["info"],
                    "msg": "Info field cannot be empty or contain only spaces.",
                    "input": info
                }]
            )
        return cleaned_info

class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: GenderEnum
    date_of_birth: date
    info: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1)
    ]
    avatar: Optional[HttpUrl]
