from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import or_, func, case, update
from typing import List, Optional, Dict
import logging

from . import models, schemas
from aetherium_gallery.features.tags.models import Tag, image_tags_association
from aetherium_gallery.utils import delete_image_files # Temporary until utils are split

logger = logging.getLogger(__name__)

async def get_image(db: AsyncSession, image_id: int) -> Optional[models.Image]:
    result = await db.execute(
        select(models.Image)
        .options(
            selectinload(models.Image.tags),
            selectinload(models.Image.album),
            selectinload(models.Image.video_source)
        )
        .filter(models.Image.id == image_id)
    )
    return result.scalars().first()

async def get_images(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100,
    safe_mode: bool = False,
    media_type: str = 'all'
) -> List[models.Image]:
    query = select(models.Image).options(
        selectinload(models.Image.tags),
        selectinload(models.Image.video_source)
    )
    if safe_mode:
        query = query.filter(models.Image.is_nsfw == False)
    if media_type == 'video':
        query = query.filter(models.Image.video_source_id.isnot(None))
    elif media_type == 'image':
        query = query.filter(models.Image.video_source_id.is_(None))
    query = query.order_by(models.Image.upload_date.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

async def create_image(db: AsyncSession, image_data: dict) -> models.Image:
    tag_names_str = image_data.pop('tags', None)
    db_image = models.Image(**image_data)
    if tag_names_str:
        tag_names = [name.strip().lower() for name in tag_names_str.split(',') if name.strip()]
        tags = await get_or_create_tags_by_name(db, tag_names)
        db_image.tags = tags
    db.add(db_image)
    await db.commit()
    await db.refresh(db_image)
    return db_image

async def update_image(db: AsyncSession, db_image: models.Image, image_update: schemas.ImageUpdate) -> models.Image:
    update_data = image_update.model_dump(exclude_unset=True)
    if 'tags' in update_data:
        tag_names_str = update_data.pop('tags')
        tag_names = [name.strip().lower() for name in tag_names_str.split(',') if name.strip()]
        if tag_names:
            tags = await get_or_create_tags_by_name(db, tag_names)
            db_image.tags = tags
        else:
            db_image.tags = []
    for key, value in update_data.items():
        setattr(db_image, key, value)
    db.add(db_image)
    await db.commit()
    await db.refresh(db_image)
    return db_image

async def delete_image(db: AsyncSession, image_id: int) -> Optional[models.Image]:
    db_image = await get_image(db, image_id)
    if db_image:
        await db.delete(db_image)
        await db.commit()
        return db_image
    return None

async def update_image_order_in_album(db: AsyncSession, album_id: int, ordered_image_ids: List[int]) -> bool:
    if not ordered_image_ids: return True
    try:
        for index, image_id in enumerate(ordered_image_ids):
            stmt = update(models.Image).where(models.Image.id == image_id).where(models.Image.album_id == album_id).values(order_index=index)
            await db.execute(stmt)
        await db.commit()
    except Exception:
        await db.rollback()
        return False
    return True

async def get_related_images(db: AsyncSession, source_image: models.Image, limit: int = 10) -> List[models.Image]:
    if not source_image.tags: return []
    source_tag_ids = {tag.id for tag in source_image.tags}
    subquery = (
        select(image_tags_association.c.image_id, func.count(image_tags_association.c.tag_id).label("match_count"))
        .where(image_tags_association.c.tag_id.in_(source_tag_ids))
        .group_by(image_tags_association.c.image_id)
        .order_by(func.count(image_tags_association.c.tag_id).desc())
        .subquery()
    )
    query = (
        select(models.Image).join(subquery, models.Image.id == subquery.c.image_id)
        .filter(models.Image.id != source_image.id)
        .options(selectinload(models.Image.tags), selectinload(models.Image.video_source))
        .order_by(subquery.c.match_count.desc()).limit(limit)
    )
    result = await db.execute(query)
    return result.scalars().all()

async def search_images(db: AsyncSession, query: str, safe_mode: bool = False, media_type: str = 'all', skip: int = 0, limit: int = 100) -> List[models.Image]:
    if not query: return []
    search_term = f"%{query}%"
    db_query = select(models.Image).filter(or_(models.Image.prompt.ilike(search_term), models.Image.negative_prompt.ilike(search_term), models.Image.original_filename.ilike(search_term)))
    db_query = db_query.options(selectinload(models.Image.tags), selectinload(models.Image.video_source))
    if safe_mode: db_query = db_query.filter(models.Image.is_nsfw == False)
    if media_type == 'video': db_query = db_query.filter(models.Image.video_source_id.isnot(None))
    elif media_type == 'image': db_query = db_query.filter(models.Image.video_source_id.is_(None))
    db_query = db_query.order_by(models.Image.upload_date.desc()).offset(skip).limit(limit)
    result = await db.execute(db_query)
    return result.scalars().all()

async def get_or_create_tags_by_name(db: AsyncSession, tag_names: List[str]) -> List[Tag]:
    existing_tags_query = await db.execute(select(Tag).where(Tag.name.in_(tag_names)))
    existing_tags = existing_tags_query.scalars().all()
    existing_tag_names = {tag.name for tag in existing_tags}
    new_tag_names = [name for name in tag_names if name not in existing_tag_names]
    new_tags = [Tag(name=name) for name in new_tag_names] if new_tag_names else []
    if new_tags: db.add_all(new_tags)
    return list(existing_tags) + new_tags

async def bulk_update_images(db: AsyncSession, action_request: schemas.BulkActionRequest) -> int:
    if not action_request.image_ids: return 0
    images_query = await db.execute(select(models.Image).options(selectinload(models.Image.tags)).filter(models.Image.id.in_(action_request.image_ids)))
    images_to_update = images_query.scalars().all()
    if action_request.action == 'add_tags' and isinstance(action_request.value, str):
        tag_names = [name.strip().lower() for name in action_request.value.split(',') if name.strip()]
        if not tag_names: return 0
        tags_to_add = await get_or_create_tags_by_name(db, tag_names)
        for image in images_to_update:
            existing_image_tags = {tag.name for tag in image.tags}
            for tag in tags_to_add:
                if tag.name not in existing_image_tags: image.tags.append(tag)
    elif action_request.action == 'set_nsfw' and isinstance(action_request.value, bool):
        for image in images_to_update: image.is_nsfw = action_request.value
    elif action_request.action == 'add_to_album':
        try:
            album_id = int(action_request.value) if action_request.value is not None else None
            for image in images_to_update: image.album_id = album_id
        except (ValueError, TypeError): return 0 
    elif action_request.action == 'delete':
        for image in images_to_update:
            delete_image_files(image.filename, image.thumbnail_path)
            await db.delete(image)
    else: return 0
    await db.commit()
    return len(images_to_update)

async def create_video_source(db: AsyncSession, video_data: dict) -> models.VideoSource:
    db_video_source = models.VideoSource(**video_data)
    db.add(db_video_source)
    await db.commit()
    await db.refresh(db_video_source)
    return db_video_source

async def batch_update_image_coordinates(db: AsyncSession, coordinates: List[Dict]) -> int:
    if not coordinates: return 0
    try:
        await db.execute(update(models.Image), coordinates)
        await db.commit()
        return len(coordinates)
    except Exception:
        await db.rollback()
        return 0

async def get_all_plotted_images(db: AsyncSession) -> List[models.Image]:
    query = select(models.Image).filter(models.Image.map_x.isnot(None), models.Image.map_y.isnot(None)).options(selectinload(models.Image.tags))
    result = await db.execute(query)
    return result.scalars().all()
