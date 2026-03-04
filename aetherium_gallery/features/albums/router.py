from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from aetherium_gallery.core.database import get_db
from . import service, schemas

router = APIRouter(
    prefix="/api/albums",
    tags=["Albums API"],
)

@router.get("/", response_model=List[schemas.AlbumInfo])
async def read_albums_api(db: AsyncSession = Depends(get_db)):
    albums_with_counts = await service.get_all_albums(db)
    # The response model is List[AlbumInfo], so we just return the Album objects
    return [a[0] for a in albums_with_counts]

@router.post("/", response_model=schemas.AlbumInfo)
async def create_album_api(album: schemas.AlbumCreate, db: AsyncSession = Depends(get_db)):
    return await service.create_album(db, album)

@router.get("/{album_id}")
async def read_album_api(album_id: int, db: AsyncSession = Depends(get_db)):
    result = await service.get_album(db, album_id)
    if not result:
        raise HTTPException(status_code=404, detail="Album not found")
    return result

@router.delete("/{album_id}", status_code=204)
async def delete_album_api(album_id: int, db: AsyncSession = Depends(get_db)):
    deleted = await service.delete_album(db, album_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Album not found")
    return None
