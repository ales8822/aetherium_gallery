# aetherium_gallery/routers/api/generation.py

import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ... import crud, schemas
from ...database import get_db
from ...config import settings

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/generation",
    tags=["Generation API"],
)

@router.post("/caption/{image_id}", status_code=200, response_model=schemas.Image)
async def generate_caption_for_image(
    request: Request,
    image_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Generates a new prompt and tags for an image using the captioning service,
    updates the database record, and returns the updated image data.
    """
    # 1. Get the captioning service from the application state
    caption_service = request.app.state.caption_service
    if not caption_service:
        raise HTTPException(status_code=503, detail="Captioning service is not available.")

    # 2. Get the image record from the database
    db_image = await crud.get_image(db, image_id=image_id)
    if not db_image:
        raise HTTPException(status_code=404, detail="Image not found")
    if db_image.video_source:
        raise HTTPException(status_code=400, detail="Cannot generate captions for video files.")

    # 3. Generate the new caption data
    image_path = settings.UPLOAD_PATH / db_image.filename
    if not image_path.exists():
        raise HTTPException(status_code=500, detail=f"Image file not found on server: {db_image.filename}")
    
    caption_data = await caption_service.generate_caption(image_path)
    if not caption_data:
        raise HTTPException(status_code=500, detail="Failed to generate caption from the AI model.")
    
    logger.info(f"Generated caption for Image ID {image_id}: {caption_data['prompt']}")

    # 4. Create an ImageUpdate schema and save the new data
    # We will also merge the new tags with any existing tags the user might have added.
    existing_tags = {tag.name for tag in db_image.tags}
    generated_tags = {tag.strip() for tag in caption_data.get('tags', '').split(',') if tag.strip()}
    
    # Combine the sets and join back into a string
    combined_tags = ", ".join(sorted(list(existing_tags.union(generated_tags))))

    update_schema = schemas.ImageUpdate(
        prompt=caption_data.get('prompt'),
        negative_prompt=caption_data.get('negative_prompt'),
        tags=combined_tags
    )
    
    updated_image = await crud.update_image(db, db_image=db_image, image_update=update_schema)

    return updated_image