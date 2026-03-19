from typing import Annotated

from fastapi import APIRouter, status, Depends, UploadFile, File, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from config import get_s3_storage_client, get_jwt_auth_manager
from database import get_db, UserModel, UserProfileModel
from exceptions import BaseSecurityError

from schemas.profiles import ProfileResponseSchema, ProfileRequestSchema, UserMeResponseSchema
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED
)
async def create_profile(
        user_id: int,
        data: ProfileRequestSchema = Depends(ProfileRequestSchema.as_form),
        db: AsyncSession = Depends(get_db),
        token: str = Depends(get_token),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        storage: S3StorageInterface = Depends(get_s3_storage_client),
):
    """
    Creates a user profile.

    Steps:
    - Validate user authentication token.
    - Check if the user already has a profile.
    - Upload avatar to S3 storage.
    - Store profile details in the database.

    Args:
        user_id (int): The ID of the user for whom the profile is being created.
        token (str): The authentication token.
        jwt_manager (JWTAuthManagerInterface): JWT manager for decoding tokens.
        db (AsyncSession): The asynchronous database session.
        s3_client (S3StorageInterface): The asynchronous S3 storage client.
        profile_data (ProfileCreateSchema): The profile data from the form.

    Returns:
        ProfileResponseSchema: The created user profile details.

    Raises:
        HTTPException: If authentication fails, if the user is not found or inactive,
                       or if the profile already exists, or if S3 upload fails.
    """
    try:
        payload = jwt_manager.decode_access_token(token)
        token_user_id = payload.get("user_id")
    except Exception as e:
        raise HTTPException(status_code=401, detail="Token has expired.")

    if token_user_id != user_id:
        res_group = await db.execute(
            select(UserModel).options(joinedload(UserModel.group)).where(UserModel.id == token_user_id)
        )
        current_user = res_group.scalar_one_or_none()
        if not current_user or current_user.group.name != "admin":
            raise HTTPException(status_code=403, detail="You don't have permission to edit this profile.")

    res_target = await db.execute(select(UserModel).where(UserModel.id == user_id))
    target_user = res_target.scalar_one_or_none()
    if not target_user or not target_user.is_active:
        raise HTTPException(status_code=401, detail="User not found or not active.")

    res_profile = await db.execute(select(UserProfileModel).where(UserProfileModel.user_id == user_id))
    if res_profile.scalars().first():
        raise HTTPException(status_code=400, detail="User already has a profile.")

    try:
        contents = await data.avatar.read()
        avatar_key = f"avatars/{user_id}_{data.avatar.filename}"
        await storage.upload_file(avatar_key, contents)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to upload avatar. Please try again later.")

    profile_data = data.model_dump()
    profile_data.pop('avatar')

    new_profile = UserProfileModel(
        user_id=user_id,
        **profile_data,
        avatar=avatar_key
    )

    db.add(new_profile)
    await db.commit()
    await db.refresh(new_profile)

    avatar_url = await storage.get_file_url(new_profile.avatar)

    return ProfileResponseSchema(
        id=new_profile.id,
        user_id=new_profile.user_id,
        first_name=new_profile.first_name,
        last_name=new_profile.last_name,
        gender=new_profile.gender,
        date_of_birth=new_profile.date_of_birth,
        info=new_profile.info,
        avatar=avatar_url
    )


@router.get(
    "/me/",
    response_model=UserMeResponseSchema,
    summary="Get Current User Profile",
    description=(
            "Retrieves the detailed profile of the currently authenticated user. "
            "Includes basic account information, the assigned user group, and profile details."
    ),
    status_code=status.HTTP_200_OK,
    responses={
        401: {"description": "Unauthorized - Invalid or expired token."},
        404: {"description": "Not Found - User not found."},
    },
)
async def get_my_profile(
        token: str = Depends(get_token),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        db: AsyncSession = Depends(get_db),
) -> UserMeResponseSchema:
    """
    Endpoint to fetch the current user's data.

    Args:
        token (str): The JWT access token from the Authorization header.
        jwt_manager (JWTAuthManagerInterface): Manager for token operations.
        db (AsyncSession): The database session.

    Returns:
        UserMeResponseSchema: Aggregated user and profile data.

    Raises:
        HTTPException: 401 if the token is invalid or 404 if the user doesn't exist.
    """
    try:
        payload = jwt_manager.decode_access_token(token)
        user_id = payload.get("user_id")
    except BaseSecurityError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token."
        )

    stmt = (
        select(UserModel)
        .options(
            joinedload(UserModel.profile),
            joinedload(UserModel.group)
        )
        .where(UserModel.id == user_id)
    )
    result = await db.execute(stmt)
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )

    return UserMeResponseSchema(
        id=user.id,
        email=user.email,
        is_active=user.is_active,
        group_name=user.group.name.value,
        created_at=user.created_at,
        profile=ProfileResponseSchema.model_validate(user.profile) if user.profile else None
    )
