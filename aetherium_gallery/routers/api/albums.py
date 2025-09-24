# aetherium_gallery/routers/api/albums.py (MERGED with DEBBUGING)

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import numpy as np
import logging

from ... import crud, schemas
from ...database import get_db
from ...services.vector_service import vector_service, _normalize_vector

router = APIRouter(
    prefix="/api/album",
    tags=["Albums API"],
)

logger = logging.getLogger(__name__)

@router.get("/{album_id}/suggestions", response_model=list[schemas.Image])
async def get_album_suggestions(album_id: int, db: AsyncSession = Depends(get_db)):
    """
    Analyzes the average aesthetic of an album and suggests other images 
    from the gallery that match this aesthetic.
    """
    logger.info("--- [Creative Director] STARTING SUGGESTION ANALYSIS ---")
    if vector_service is None:
        logger.error("[Creative Director] Vector service is not available.")
        raise HTTPException(status_code=503, detail="Vector service is not available.")

    # 1. Get the IDs of all images currently in the album
    image_ids_in_album = await crud.get_image_ids_for_album(db, album_id=album_id)
    if not image_ids_in_album:
        logger.info(f"[Creative Director] Album {album_id} is empty. No suggestions to generate.")
        return []
    logger.info(f"[Creative Director] Found {len(image_ids_in_album)} images in album {album_id}: {image_ids_in_album}")

    # 2. Get the vector embeddings for all images in the album
    embeddings = vector_service.get_embeddings_for_ids(image_ids_in_album)
    if embeddings is None or len(embeddings) == 0:
        logger.warning(f"[Creative Director] No valid embeddings found for images in album {album_id}. Cannot continue.")
        return []
    logger.info(f"[Creative Director] Retrieved {embeddings.shape[0]} embeddings from vector service.")
    
    # 3. Calculate the "average aesthetic" vector
    average_vector = np.mean(embeddings, axis=0)
    normalized_average_vector = _normalize_vector(average_vector)
    logger.info(f"[Creative Director] Calculated normalized average vector. Shape: {normalized_average_vector.shape}")

    # 4. Use the average vector to search for similar images
    # Exclude images that are already in the album
    suggested_ids = vector_service.find_similar_images_by_vector(
        query_vector=normalized_average_vector,
        exclude_ids=image_ids_in_album,
        n_results=24
    )

    if not suggested_ids:
        logger.warning("[Creative Director] Vector search returned no suggestions. Check similarity scores in vector_service logs.")
        return []
    logger.info(f"[Creative Director] Vector search found {len(suggested_ids)} potential suggestions: {suggested_ids}")

    # 5. Fetch the full image data for the suggested IDs
    suggested_images = await crud.get_images_by_ids(db, image_ids=suggested_ids)
    logger.info(f"[Creative Director] Fetched full data for {len(suggested_images)} images from database.")
    logger.info("--- [Creative Director] ANALYSIS COMPLETE ---")
    
    return suggested_images

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
        raise HTTPException(status_code=500, detail="An unexpected error occurred while reordering.")