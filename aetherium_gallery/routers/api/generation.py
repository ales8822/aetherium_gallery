# aetherium_gallery/routers/api/generation.py (UPDATED)

import logging
import asyncio
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Literal, Optional
import tempfile
from pathlib import Path
from fastapi import UploadFile, File, Form
from ... import crud, schemas
from ...database import get_db
from ...config import settings

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/generation",
    tags=["Generation API"],
)
# Add this new response schema
class GeneratedContentResponse(BaseModel):
    prompt: Optional[str] = None
    tags: Optional[str] = None

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

@router.post("/generate-for-upload", response_model=GeneratedContentResponse)
async def generate_content_for_upload(
    request: Request,
    file: UploadFile = File(...),
    generate_description: bool = Form(False),
    generate_tags: bool = Form(False)
):
    """
    Receives a temporary image file, runs the requested AI services,
    and returns the generated text without saving anything.
    """
    caption_service = request.app.state.caption_service
    if not caption_service:
        raise HTTPException(status_code=503, detail="Captioning service is not available.")

    # We will manually create and delete the temp file to control its lifecycle.
    temp_path: Optional[Path] = None
    try:
        # 1. Create a unique path in the system's temp directory.
        temp_dir = Path(tempfile.gettempdir())
        temp_filename = f"{uuid.uuid4()}{Path(file.filename).suffix}"
        temp_path = temp_dir / temp_filename
        
        # 2. Write the file content and ensure it's closed immediately.
        with open(temp_path, "wb") as buffer:
            buffer.write(await file.read())
        
        # 3. Now that the file is closed, we can safely pass its path to other services.
        tasks_to_run = []
        if generate_description:
            tasks_to_run.append(caption_service.generate_gemini_description(temp_path))
        if generate_tags:
            tasks_to_run.append(caption_service.generate_wd14_tags(temp_path))

        if not tasks_to_run:
            return GeneratedContentResponse()

        results = await asyncio.gather(*tasks_to_run, return_exceptions=True)
        
        response_data = {}
        result_index = 0
        if generate_description:
            desc_result = results[result_index]
            if isinstance(desc_result, str):
                response_data["prompt"] = desc_result
            else:
                logger.error(f"Upload-gen Gemini failed: {desc_result}")
            result_index += 1
        
        if generate_tags:
            tags_result = results[result_index]
            if isinstance(tags_result, str):
                response_data["tags"] = tags_result
            else:
                logger.error(f"Upload-gen WD14 failed: {tags_result}")

        return GeneratedContentResponse(**response_data)

    except Exception as e:
        logger.error(f"Error during upload generation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate content from image.")
    finally:
        # 4. CRITICAL: Ensure the temporary file is deleted after we're done.
        if temp_path and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError as e:
                logger.error(f"Failed to delete temporary file {temp_path}: {e}")