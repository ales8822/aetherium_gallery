# aetherium_gallery/routers/api/images_api.py
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from ...database import get_db
from typing import List # Import List for the response model
from ... import crud, schemas # Import schemas


router = APIRouter(
    prefix="/api/images",
    tags=["Images API (New)"]
)

@router.get("/{image_id}/similar", response_model=List[schemas.Image])
async def find_similar_images_api(
    # ▼▼▼ ADD 'request: Request' HERE ▼▼▼
    request: Request,
    image_id: int, 
    db: AsyncSession = Depends(get_db)
):
    # Now this line will work correctly
    vector_service = request.app.state.vector_service

    if not vector_service:
        raise HTTPException(status_code=503, detail="Visual search service is not available.")
    
    similar_ids = vector_service.find_similar_images(image_id)
    if not similar_ids:
        return []
    
    similar_images = await crud.get_images_by_ids(db, image_ids=similar_ids)
    
    id_map = {img.id: img for img in similar_images}
    sorted_images = [id_map[id] for id in similar_ids if id in id_map]
    
    return sorted_images