# aetherium_gallery/routers/api/tasks.py (NEW FILE)
import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
import umap
import numpy as np
from typing import List
from ... import crud
from ... import schemas
from ...database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tasks", tags=["Background Tasks API"])

@router.post("/calculate-map", status_code=200)
async def calculate_constellation_map(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Recalculates the 2D coordinates for the Constellation Map for all images.
    This is a long-running, resource-intensive task.
    """
    logger.info("Starting Constellation Map calculation...")
    vector_service = request.app.state.vector_service
    if not vector_service:
        raise HTTPException(status_code=503, detail="Vector Service is not available.")

    # 1. Export all vectors and their IDs from the vector service
    all_vectors, all_ids = vector_service.get_all_vectors()
    
    if all_vectors is None or len(all_ids) < 3: # UMAP needs at least a few points
        msg = "Not enough indexed images to generate a map (need at least 3)."
        logger.warning(msg)
        return {"message": msg, "images_mapped": 0}

    logger.info(f"Retrieved {len(all_ids)} vectors. Running UMAP dimensionality reduction...")

    try:
        # 2. Run the UMAP algorithm
        # These are standard parameters that work well for visualization.
        reducer = umap.UMAP(
            n_neighbors=15,    # Balances local vs. global structure
            min_dist=0.1,      # How tightly points are packed
            n_components=2,    # We want a 2D map (x, y)
            metric='cosine',   # Cosine similarity is great for normalized vectors like ours
            random_state=42    # Ensures the map is reproducible
        )
        
        # This is the core calculation
        embedding_2d = reducer.fit_transform(all_vectors)

        logger.info("UMAP calculation complete. Preparing data for database update.")

        # 3. Prepare the data for batch updating
        coordinates_to_update = [
            {"id": img_id, "map_x": float(coords[0]), "map_y": float(coords[1])}
            for img_id, coords in zip(all_ids, embedding_2d)
        ]

        # 4. Save the new coordinates to the database
        updated_count = await crud.batch_update_image_coordinates(db, coordinates=coordinates_to_update)

        if updated_count > 0:
            msg = f"Successfully calculated and saved map coordinates for {updated_count} images."
            logger.info(msg)
            return {"message": msg, "images_mapped": updated_count}
        else:
            msg = "UMAP calculation ran, but failed to save coordinates to the database."
            logger.error(msg)
            raise HTTPException(status_code=500, detail=msg)
            
    except Exception as e:
        logger.error(f"An error occurred during map calculation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An error occurred during map calculation: {str(e)}")
    

@router.get("/map-data", response_model=List[schemas.Image])
async def get_constellation_map_data(db: AsyncSession = Depends(get_db)):
    """
    Fetches all images that have been plotted on the Constellation Map
    and returns their data for frontend visualization.
    """
    logger.info("Fetching all plotted images for the Constellation Map.")
    plotted_images = await crud.get_all_plotted_images(db)
    return plotted_images