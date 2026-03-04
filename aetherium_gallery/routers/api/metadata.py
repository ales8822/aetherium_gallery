# aetherium_gallery/routers/api/metadata.py

import json
import logging
import os
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from PIL import Image as PILImage, PngImagePlugin

# --- NEW ARCHITECTURE IMPORTS ---
from ...core.database import get_db
from ...core.config import settings
from ...features.images import service as image_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/embedded-data", tags=["Embedded File Data API"])

# Our special key for the embedded data
METADATA_KEY = "aetherium_gallery_data"

# Schemas are now simpler and kept local since they are specific to this endpoint
class EmbeddedDataResponse(BaseModel):
    user_data: Dict[str, Any]
    tech_data: Dict[str, Any]

class EmbeddedDataUpdateRequest(BaseModel):
    user_data: Dict[str, Any]

# --- Main API Endpoints ---

@router.get("/{image_id}", response_model=EmbeddedDataResponse)
async def get_embedded_data(image_id: int, db: AsyncSession = Depends(get_db)):
    # REPLACEMENT: image_service
    db_image = await image_service.get_image(db, image_id=image_id)
    if not db_image:
        raise HTTPException(status_code=404, detail="Image not found")
        
    file_path = settings.UPLOAD_PATH / db_image.filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Image file not found on server.")

    def read_data_from_image():
        try:
            with PILImage.open(file_path) as img:
                # Get all available metadata
                tech_data_raw = img.info or {}
                
                # Try to extract our special data chunk
                user_data_str = tech_data_raw.get(METADATA_KEY, '{}')
                user_data = {}
                try:
                    if isinstance(user_data_str, str):
                        user_data = json.loads(user_data_str)
                except (json.JSONDecodeError, TypeError):
                    logger.warning(f"Could not parse custom data for image {image_id}")

                # Clean up technical data to be JSON-serializable
                # We exclude our custom key from tech_data to avoid duplication
                tech_data = {
                    k: str(v) for k, v in tech_data_raw.items() 
                    if k != METADATA_KEY and isinstance(v, (str, int, float))
                }
                
                return {"user_data": user_data, "tech_data": tech_data}
        except Exception as e:
            logger.error(f"Pillow failed to read image data: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to read image file.")

    return await run_in_threadpool(read_data_from_image)


@router.patch("/{image_id}", status_code=200)
async def update_embedded_data(
    image_id: int, 
    request: EmbeddedDataUpdateRequest, 
    db: AsyncSession = Depends(get_db)
):
    # REPLACEMENT: image_service
    db_image = await image_service.get_image(db, image_id=image_id)
    if not db_image:
        raise HTTPException(status_code=404, detail="Image not found")
        
    file_path = settings.UPLOAD_PATH / db_image.filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Image file not found.")

    def write_data_to_image():
        try:
            # We open the image to read current info
            # Note: We are not using 'with' here because we might need to save over it,
            # but usually safely saving to a temp file is better.
            with PILImage.open(file_path) as img:
                img.load() # Ensure image data is loaded into memory
                
                # Get existing metadata
                metadata = img.info.copy()
                
                # Serialize our new user data
                user_data_json = json.dumps(request.user_data)
                metadata[METADATA_KEY] = user_data_json

                # Create a temporary file to save to
                temp_path = file_path.with_suffix(f".tmp{file_path.suffix}")

                # Save logic based on format
                if img.format == "PNG":
                    png_info = PngImagePlugin.PngInfo()
                    for key, value in metadata.items():
                        png_info.add_text(key, str(value))
                    img.save(temp_path, "PNG", pnginfo=png_info)
                    
                elif img.format in ["JPEG", "JPG"]:
                    # For JPEG, we pass extra args as kwargs, but need to handle exif separately
                    exif_data = img.getexif() 
                    img.save(temp_path, "JPEG", quality=95, exif=exif_data, **metadata)
                    
                elif img.format == "WEBP":
                    exif_bytes = img.info.get("exif", b"")
                    # WebP supports metadata in a specific way, often passed as kwargs
                    img.save(temp_path, "WEBP", quality=95, exif=exif_bytes)
                    # Note: Embedding custom text chunks in WebP via Pillow can be tricky.
                    # This might require specific handling if METADATA_KEY isn't saved automatically.
                else:
                    raise HTTPException(status_code=400, detail=f"Unsupported format for metadata writing: {img.format}")

            # If save was successful (no exception), atomically replace the original file
            os.replace(temp_path, file_path)
            
            return {"message": "Embedded metadata updated successfully."}
            
        except Exception as e:
            # Clean up temp file if it exists
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.remove(temp_path)
                
            logger.error(f"Pillow failed to write image data: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to write to image file.")

    return await run_in_threadpool(write_data_to_image)