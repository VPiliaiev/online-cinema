from pydantic import BaseModel, EmailStr, field_validator

from database import accounts_validators


class PasswordResetRequestSchema(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def validate_email_field(cls, value: str) -> str:
        return accounts_validators.validate_email(value)


class UserLoginRequestSchema(BaseModel):
    email: EmailStr
    password: str

    model_config = {"from_attributes": True}

    @field_validator("email")
    @classmethod
    def validate_email_field(cls, value: str) -> str:
        return accounts_validators.validate_email(value)


class UserRegistrationRequestSchema(UserLoginRequestSchema):
    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        return accounts_validators.validate_password_strength(value)


class PasswordResetCompleteRequestSchema(UserRegistrationRequestSchema):
    token: str


class UserLoginResponseSchema(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserRegistrationResponseSchema(BaseModel):
    id: int
    email: EmailStr

    model_config = {
        "from_attributes": True
    }


class UserActivationRequestSchema(BaseModel):
    email: EmailStr
    token: str


class MessageResponseSchema(BaseModel):
    message: str


class TokenRefreshRequestSchema(BaseModel):
    refresh_token: str


class TokenRefreshResponseSchema(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PasswordChangeRequestSchema(BaseModel):
    old_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        return accounts_validators.validate_password_strength(value)
