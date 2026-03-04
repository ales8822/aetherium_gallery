from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import func, case, update
from typing import List, Optional, Dict
import logging

from . import models, schemas
from aetherium_gallery.features.images.models import Image

logger = logging.getLogger(__name__)

async def get_album(db: AsyncSession, album_id: int) -> Optional[dict]:
    album_result = await db.execute(select(models.Album).filter(models.Album.id == album_id))
    album = album_result.scalars().first()
    if not album: return None
    images_result = await db.execute(
        select(Image).filter(Image.album_id == album_id)
        .options(selectinload(Image.tags), selectinload(Image.video_source))
        .order_by(Image.order_index)
    )
    images = images_result.scalars().all()
    return {"album": album, "images": images}

async def get_all_albums(db: AsyncSession) -> List:
    image_count_subquery = (
        select(Image.album_id, func.count(Image.id).label("image_count"))
        .group_by(Image.album_id).subquery()
    )
    query = (
        select(models.Album, func.coalesce(image_count_subquery.c.image_count, 0))
        .outerjoin(image_count_subquery, models.Album.id == image_count_subquery.c.album_id)
        .order_by(models.Album.name)
    )
    result = await db.execute(query)
    return result.all()
    
async def create_album(db: AsyncSession, album: schemas.AlbumCreate) -> models.Album:
    db_album = models.Album(name=album.name, description=album.description)
    db.add(db_album)
    await db.commit()
    await db.refresh(db_album)
    return db_album

async def delete_album(db: AsyncSession, album_id: int) -> Optional[models.Album]:
    db_album_data = await get_album(db, album_id=album_id)
    if db_album_data:
        db_album = db_album_data['album']
        await db.delete(db_album)
        await db.commit()
        return db_album
    return None
