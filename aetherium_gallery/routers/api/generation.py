# aetherium_gallery/routers/api/generation.py (UPDATED)

import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Literal

from ... import crud, schemas
from ...database import get_db
from ...config import settings

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/generation",
    tags=["Generation API"],
)

# Define a schema for the incoming request body
class GenerationRequest(BaseModel):
    source: Literal['gemini', 'wd14', 'all']

@router.post("/caption/{image_id}", status_code=200, response_model=schemas.Image)
async def generate_caption_for_image(
    request: Request,
    image_id: int,
    gen_request: GenerationRequest, # The endpoint now expects the new request body
    db: AsyncSession = Depends(get_db)
):
    """
    Generates either a description (from Gemini) or tags (from WD14) for an image,
    updates the database record, and returns the updated image data.
    """
    # 1. Get the captioning service and image record
    caption_service = request.app.state.caption_service
    if not caption_service:
        raise HTTPException(status_code=503, detail="Captioning service is not available.")

    db_image = await crud.get_image(db, image_id=image_id)
    if not db_image:
        raise HTTPException(status_code=404, detail="Image not found")
    if db_image.video_source:
        raise HTTPException(status_code=400, detail="Cannot generate metadata for video files.")

    image_path = settings.UPLOAD_PATH / db_image.filename
    if not image_path.exists():
        raise HTTPException(status_code=500, detail=f"Image file not found on server: {db_image.filename}")
    
    update_data = {}

    # ▼▼▼ 2. UPDATE THE LOGIC TO HANDLE 'all' ▼▼▼
    if gen_request.source == 'all':
        logger.info(f"Generating ALL metadata for Image ID {image_id}...")
        # Call the original combined method from the service
        all_data = await caption_service.generate_caption(image_path)
        if not all_data:
            raise HTTPException(status_code=500, detail="Failed to generate combined metadata.")
        
        # Merge new tags with existing ones
        existing_tags = {tag.name for tag in db_image.tags}
        generated_tags = {tag.strip().lower() for tag in all_data.get('tags', '').split(',') if tag.strip()}
        combined_tags = ", ".join(sorted(list(existing_tags.union(generated_tags))))
        
        update_data = {
            "prompt": all_data.get('prompt'), # Use the full prompt from the service
            "tags": combined_tags
        }
    # 2. Call the correct service based on the 'source' from the request body
    elif gen_request.source == 'gemini':
        logger.info(f"Generating Gemini description for Image ID {image_id}...")
        description = await caption_service.generate_gemini_description(image_path)
        if not description:
            raise HTTPException(status_code=500, detail="Failed to generate description from Gemini.")
        logger.info(f"Generated Gemini description for Image ID {image_id}")
        update_data['prompt'] = description # We only update the prompt

    elif gen_request.source == 'wd14':
        logger.info(f"Generating WD14 tags for Image ID {image_id}...")
        tags_str = await caption_service.generate_wd14_tags(image_path)
        if not tags_str:
            raise HTTPException(status_code=500, detail="Failed to generate tags from WD14 Tagger.")
        logger.info(f"Generated WD14 tags for Image ID {image_id}")
        
        # Merge new tags with existing ones, avoiding duplicates
        existing_tags = {tag.name for tag in db_image.tags}
        generated_tags = {tag.strip().lower() for tag in tags_str.split(',') if tag.strip()}
        combined_tags = ", ".join(sorted(list(existing_tags.union(generated_tags))))
        update_data['tags'] = combined_tags # We only update the tags

    # 3. If data was generated, create an update schema and save it
    if not update_data:
        raise HTTPException(status_code=400, detail="Invalid generation source provided.")
        
    update_schema = schemas.ImageUpdate(**update_data)
    updated_image = await crud.update_image(db, db_image=db_image, image_update=update_schema)

    return updated_image