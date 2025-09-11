# aetherium_gallery/routers/api/albums.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from ... import crud, schemas
from ...database import get_db

router = APIRouter(
    prefix="/api/album",
    tags=["Album API"],
)

@router.post("/{album_id}/reorder", status_code=200)
async def reorder_album_images(
    album_id: int,
    reorder_request: schemas.AlbumReorderRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Receives a new order of image IDs and updates their order_index in the database.
    """
    if not reorder_request.image_ids:
        return {"message": "No image IDs provided."}

    success = await crud.update_image_order_in_album(
        db, album_id=album_id, ordered_image_ids=reorder_request.image_ids
    )

    if success:
        return {"message": f"Successfully reordered {len(reorder_request.image_ids)} images in album {album_id}."}
    else:
        # This part of the code might not be reachable with current logic,
        # but it's good practice to have it.
        raise HTTPException(status_code=500, detail="An unexpected error occurred while reordering.")