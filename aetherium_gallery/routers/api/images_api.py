# aetherium_gallery/routers/api/images_api.py

from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

# --- NEW ARCHITECTURE IMPORTS ---
from ...core.database import get_db
from ...features.images import schemas as image_schemas
from ...features.images import service as image_service

router = APIRouter(
    prefix="/api/images",
    tags=["Images API (New)"]
)

@router.get("/{image_id}/similar", response_model=List[image_schemas.Image])
async def find_similar_images_api(
    request: Request,
    image_id: int, 
    db: AsyncSession = Depends(get_db)
):
    """
    Finds images similar to the given image_id using the Vector Service.
    """
    vector_service = request.app.state.vector_service

    if not vector_service:
        raise HTTPException(status_code=503, detail="Visual search service is not available.")
    
    # Get similar IDs from FAISS/DINOv2
    similar_ids = vector_service.find_similar_images(image_id)
    
    if not similar_ids:
        return []
    
    # Fetch full image objects from Database
    similar_images = await image_service.get_images_by_ids(db, image_ids=similar_ids)
    
    # Sort them to match the order returned by the vector service (most similar first)
    id_map = {img.id: img for img in similar_images}
    sorted_images = [id_map[id] for id in similar_ids if id in id_map]
    
    return sorted_images