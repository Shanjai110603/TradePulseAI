from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import verify_password, get_password_hash, create_access_token, oauth2_scheme
from app.models.user import User, UserPreferences
from app.models.telegram import TelegramAccount
from app.schemas.auth import UserCreate, UserLogin, UserResponse, Token, UserPreferencesSchema
from jose import jwt, JWTError
from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])


async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    from sqlalchemy.orm import selectinload
    query = select(User).where(User.id == user_id).options(selectinload(User.preferences))
    res = await db.execute(query)
    user = res.scalar_one_or_none()
    if user is None or not user.is_active:
        raise credentials_exception
    return user


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    query = select(User).where(User.email == user_in.email)
    res = await db.execute(query)
    if res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="An account with this email already exists")

    new_user = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name,
        timezone=user_in.timezone
    )
    db.add(new_user)
    await db.flush()

    # Create default user preferences
    prefs = UserPreferences(user_id=new_user.id)
    db.add(prefs)
    await db.commit()
    await db.refresh(new_user)

    access_token = create_access_token(subject=new_user.id)
    
    user_resp = UserResponse(
        id=new_user.id,
        email=new_user.email,
        full_name=new_user.full_name,
        timezone=new_user.timezone,
        is_active=new_user.is_active,
        is_admin=new_user.is_admin,
        created_at=new_user.created_at,
        is_telegram_linked=False,
        preferences=UserPreferencesSchema.model_validate(prefs)
    )

    return Token(access_token=access_token, token_type="bearer", user=user_resp)


@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    from sqlalchemy.orm import selectinload
    query = select(User).where(User.email == form_data.username).options(selectinload(User.preferences))
    res = await db.execute(query)
    user = res.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")

    access_token = create_access_token(subject=user.id)

    # Check telegram link
    tg_q = select(TelegramAccount).where(TelegramAccount.user_id == user.id, TelegramAccount.is_active == True)
    tg_res = await db.execute(tg_q)
    is_tg = tg_res.scalar_one_or_none() is not None

    user_resp = UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        timezone=user.timezone,
        is_active=user.is_active,
        is_admin=user.is_admin,
        created_at=user.created_at,
        is_telegram_linked=is_tg,
        preferences=UserPreferencesSchema.model_validate(user.preferences) if user.preferences else None
    )

    return Token(access_token=access_token, token_type="bearer", user=user_resp)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    tg_q = select(TelegramAccount).where(TelegramAccount.user_id == current_user.id, TelegramAccount.is_active == True)
    tg_res = await db.execute(tg_q)
    is_tg = tg_res.scalar_one_or_none() is not None

    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        timezone=current_user.timezone,
        is_active=current_user.is_active,
        is_admin=current_user.is_admin,
        created_at=current_user.created_at,
        is_telegram_linked=is_tg,
        preferences=UserPreferencesSchema.model_validate(current_user.preferences) if current_user.preferences else None
    )


@router.put("/preferences", response_model=UserPreferencesSchema)
async def update_preferences(
    prefs_in: UserPreferencesSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(UserPreferences).where(UserPreferences.user_id == current_user.id)
    res = await db.execute(query)
    prefs = res.scalar_one_or_none()

    if not prefs:
        prefs = UserPreferences(user_id=current_user.id)
        db.add(prefs)

    for k, v in prefs_in.model_dump().items():
        setattr(prefs, k, v)

    await db.commit()
    await db.refresh(prefs)
    return UserPreferencesSchema.model_validate(prefs)
