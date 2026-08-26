import os
import uuid
import aiofiles
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.user import User
from app.models.pattern import Pattern, PatternImage, PatternVersion
from app.schemas.pattern import PatternCreate, PatternUpdate, PatternResponse, PatternVersionResponse, PatternImageResponse

router = APIRouter(prefix="/patterns", tags=["Patterns & Strategies"])


@router.get("", response_model=List[PatternResponse])
async def list_user_patterns(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = (
        select(Pattern)
        .where(Pattern.user_id == current_user.id)
        .options(selectinload(Pattern.images))
        .order_by(desc(Pattern.created_at))
    )
    res = await db.execute(query)
    patterns = res.scalars().all()
    return patterns


@router.post("", response_model=PatternResponse, status_code=status.HTTP_201_CREATED)
async def create_pattern(
    pattern_in: PatternCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    new_pattern = Pattern(
        user_id=current_user.id,
        name=pattern_in.name,
        description=pattern_in.description,
        market_id=pattern_in.market_id,
        direction=pattern_in.direction,
        timeframe=pattern_in.timeframe,
        is_active=pattern_in.is_active,
        current_version=1,
        assets_config=pattern_in.assets_config,
        timeframes_config=pattern_in.timeframes_config,
        trend_config=pattern_in.trend_config.model_dump(),
        momentum_config=pattern_in.momentum_config.model_dump(),
        volume_config=pattern_in.volume_config.model_dump(),
        indicators_config=[i.model_dump() for i in pattern_in.indicators_config],
        rules_config=pattern_in.rules_config,
        entry_config=pattern_in.entry_config.model_dump(),
        target_config=pattern_in.target_config.model_dump(),
        ai_config=pattern_in.ai_config.model_dump(),
        notification_config=pattern_in.notification_config.model_dump(),
    )
    db.add(new_pattern)
    await db.flush()

    # Create initial version v1 snapshot
    v1 = PatternVersion(
        pattern_id=new_pattern.id,
        version_number=1,
        change_summary="Initial pattern creation",
        config_snapshot=pattern_in.model_dump()
    )
    db.add(v1)

    await db.commit()
    await db.refresh(new_pattern)
    
    # Reload with images
    res = await db.execute(select(Pattern).where(Pattern.id == new_pattern.id).options(selectinload(Pattern.images)))
    return res.scalar_one()


@router.get("/{pattern_id}", response_model=PatternResponse)
async def get_pattern(
    pattern_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = (
        select(Pattern)
        .where(Pattern.id == pattern_id, Pattern.user_id == current_user.id)
        .options(selectinload(Pattern.images))
    )
    res = await db.execute(query)
    pattern = res.scalar_one_or_none()
    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")
    return pattern


@router.put("/{pattern_id}", response_model=PatternResponse)
async def update_pattern(
    pattern_id: str,
    update_in: PatternUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(Pattern).where(Pattern.id == pattern_id, Pattern.user_id == current_user.id)
    res = await db.execute(query)
    pattern = res.scalar_one_or_none()
    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")

    # Increment version
    pattern.current_version += 1
    
    update_data = update_in.model_dump(exclude_unset=True)
    change_summary = update_data.pop("change_summary", f"Updated to v{pattern.current_version}")

    for k, v in update_data.items():
        if v is not None:
            if hasattr(v, "model_dump"):
                setattr(pattern, k, v.model_dump())
            else:
                setattr(pattern, k, v)

    # Save version record
    v_record = PatternVersion(
        pattern_id=pattern.id,
        version_number=pattern.current_version,
        change_summary=change_summary,
        config_snapshot=update_in.model_dump()
    )
    db.add(v_record)

    await db.commit()
    await db.refresh(pattern)
    
    res = await db.execute(select(Pattern).where(Pattern.id == pattern.id).options(selectinload(Pattern.images)))
    return res.scalar_one()


@router.post("/{pattern_id}/toggle", response_model=PatternResponse)
async def toggle_pattern_status(
    pattern_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(Pattern).where(Pattern.id == pattern_id, Pattern.user_id == current_user.id)
    res = await db.execute(query)
    pattern = res.scalar_one_or_none()
    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")

    pattern.is_active = not pattern.is_active
    await db.commit()
    await db.refresh(pattern)

    res = await db.execute(select(Pattern).where(Pattern.id == pattern.id).options(selectinload(Pattern.images)))
    return res.scalar_one()


@router.post("/{pattern_id}/image", response_model=PatternImageResponse)
async def upload_pattern_image(
    pattern_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(Pattern).where(Pattern.id == pattern_id, Pattern.user_id == current_user.id)
    res = await db.execute(query)
    pattern = res.scalar_one_or_none()
    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")

    if file.content_type not in settings.ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid file type. Allowed: {settings.ALLOWED_IMAGE_TYPES}")

    # Read and enforce file size
    contents = await file.read()
    if len(contents) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB}MB")

    ext = os.path.splitext(file.filename or "image.png")[1]
    safe_filename = f"{pattern_id}_{uuid.uuid4().hex[:8]}{ext}"
    dest_path = os.path.join(settings.UPLOAD_DIR, safe_filename)

    async with aiofiles.open(dest_path, "wb") as f:
        await f.write(contents)

    img = PatternImage(
        pattern_id=pattern.id,
        file_path=f"/{settings.UPLOAD_DIR}/{safe_filename}",
        filename=file.filename or safe_filename,
        mime_type=file.content_type,
        file_size_bytes=len(contents),
        is_primary=True
    )
    db.add(img)
    await db.commit()
    await db.refresh(img)
    return img


@router.get("/{pattern_id}/versions", response_model=List[PatternVersionResponse])
async def list_pattern_versions(
    pattern_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = (
        select(PatternVersion)
        .where(PatternVersion.pattern_id == pattern_id)
        .order_by(desc(PatternVersion.version_number))
    )
    res = await db.execute(query)
    return res.scalars().all()


@router.post("/{pattern_id}/duplicate", response_model=PatternResponse)
async def duplicate_pattern(
    pattern_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(Pattern).where(Pattern.id == pattern_id, Pattern.user_id == current_user.id)
    res = await db.execute(query)
    orig = res.scalar_one_or_none()
    if not orig:
        raise HTTPException(status_code=404, detail="Pattern not found")

    dup = Pattern(
        user_id=current_user.id,
        name=f"{orig.name} (Copy)",
        description=orig.description,
        market_id=orig.market_id,
        direction=orig.direction,
        timeframe=orig.timeframe,
        is_active=False,  # default inactive
        current_version=1,
        assets_config=orig.assets_config,
        timeframes_config=orig.timeframes_config,
        trend_config=orig.trend_config,
        momentum_config=orig.momentum_config,
        volume_config=orig.volume_config,
        indicators_config=orig.indicators_config,
        rules_config=orig.rules_config,
        entry_config=orig.entry_config,
        target_config=orig.target_config,
        ai_config=orig.ai_config,
        notification_config=orig.notification_config
    )
    db.add(dup)
    await db.flush()

    v1 = PatternVersion(
        pattern_id=dup.id,
        version_number=1,
        change_summary=f"Cloned from {orig.name}",
        config_snapshot={"source_id": orig.id}
    )
    db.add(v1)
    await db.commit()
    await db.refresh(dup)

    res = await db.execute(select(Pattern).where(Pattern.id == dup.id).options(selectinload(Pattern.images)))
    return res.scalar_one()


@router.delete("/{pattern_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pattern(
    pattern_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(Pattern).where(Pattern.id == pattern_id, Pattern.user_id == current_user.id)
    res = await db.execute(query)
    pattern = res.scalar_one_or_none()
    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")

    await db.delete(pattern)
    await db.commit()
    return None
