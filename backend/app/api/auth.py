from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
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


async def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required"
        )
    return current_user


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
async def login(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    from sqlalchemy.orm import selectinload
    email = None
    password = None

    # 1. Try parsing JSON body
    try:
        body = await request.json()
        if isinstance(body, dict):
            email = body.get("email") or body.get("username")
            password = body.get("password")
    except Exception:
        pass

    # 2. Try parsing Form / Multipart if JSON was not present
    if not email or not password:
        try:
            form = await request.form()
            email = form.get("username") or form.get("email")
            password = form.get("password")
        except Exception:
            pass

    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required")

    clean_email = email.strip().lower()
    clean_password = password.strip() if isinstance(password, str) else password

    query = select(User).where(User.email == clean_email).options(selectinload(User.preferences))
    res = await db.execute(query)
    user = res.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=400, detail="Invalid email or password")

    if not verify_password(clean_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Invalid email or password")

    access_token = create_access_token(subject=user.id)

    # Check telegram link
    tg_q = select(TelegramAccount).where(TelegramAccount.user_id == user.id, TelegramAccount.is_active == True)
    tg_res = await db.execute(tg_q)
    is_tg = tg_res.scalar_one_or_none() is not None

    prefs_schema = None
    try:
        if user.preferences:
            prefs_schema = UserPreferencesSchema.model_validate(user.preferences)
    except Exception:
        pass

    user_resp = UserResponse(
        id=str(user.id),
        email=user.email or clean_email,
        full_name=user.full_name or "Demo User",
        timezone=user.timezone or "UTC",
        is_active=True,
        is_admin=bool(user.is_admin),
        created_at=user.created_at or datetime.utcnow(),
        is_telegram_linked=is_tg,
        preferences=prefs_schema
    )

    return Token(access_token=access_token, token_type="bearer", user=user_resp)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    tg_q = select(TelegramAccount).where(TelegramAccount.user_id == current_user.id, TelegramAccount.is_active == True)
    tg_res = await db.execute(tg_q)
    is_tg = tg_res.scalar_one_or_none() is not None

    prefs_schema = None
    try:
        if current_user.preferences:
            prefs_schema = UserPreferencesSchema.model_validate(current_user.preferences)
    except Exception:
        pass

    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        full_name=current_user.full_name,
        timezone=current_user.timezone or "UTC",
        is_active=current_user.is_active,
        is_admin=current_user.is_admin,
        created_at=current_user.created_at or datetime.utcnow(),
        is_telegram_linked=is_tg,
        preferences=prefs_schema
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
