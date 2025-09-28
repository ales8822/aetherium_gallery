# aetherium_gallery/routers/api/metadata.py (NEW Pillow-based Implementation)

import json
import logging
import os
import re
from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from PIL import Image as PILImage, PngImagePlugin, JpegImagePlugin

from ... import crud
from ...database import get_db
from ...config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/embedded-data", tags=["Embedded File Data API"]) # New prefix

# Our special key for the embedded data
METADATA_KEY = "aetherium_gallery_data"

# Schemas are now simpler
class EmbeddedDataResponse(BaseModel):
    user_data: Dict[str, Any]
    tech_data: Dict[str, Any]

class EmbeddedDataUpdateRequest(BaseModel):
    user_data: Dict[str, str]

# --- Main API Endpoints ---

@router.get("/{image_id}", response_model=EmbeddedDataResponse)
async def get_embedded_data(image_id: int, db: AsyncSession = Depends(get_db)):
    db_image = await crud.get_image(db, image_id=image_id)
    if not db_image: raise HTTPException(status_code=404, detail="Image not found")
    file_path = settings.UPLOAD_PATH / db_image.filename
    if not file_path.exists(): raise HTTPException(status_code=404, detail="Image file not found on server.")

    def read_data_from_image():
        try:
            with PILImage.open(file_path) as img:
                # Get all available metadata
                tech_data_raw = img.info or {}
                
                # Try to extract our special data chunk
                user_data_str = tech_data_raw.pop(METADATA_KEY, '{}')
                user_data = {}
                try:
                    user_data = json.loads(user_data_str)
                except (json.JSONDecodeError, TypeError):
                    logger.warning(f"Could not parse custom data for image {image_id}")

                # Clean up technical data to be JSON-serializable
                tech_data = {k: str(v) for k, v in tech_data_raw.items() if isinstance(v, (str, int, float))}
                
                return {"user_data": user_data, "tech_data": tech_data}
        except Exception as e:
            logger.error(f"Pillow failed to read image data: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to read image file.")

    return await run_in_threadpool(read_data_from_image)


@router.patch("/{image_id}", status_code=200)
async def update_embedded_data(image_id: int, request: EmbeddedDataUpdateRequest, db: AsyncSession = Depends(get_db)):
    db_image = await crud.get_image(db, image_id=image_id)
    if not db_image: raise HTTPException(status_code=404, detail="Image not found")
    file_path = settings.UPLOAD_PATH / db_image.filename
    if not file_path.exists(): raise HTTPException(status_code=404, detail="Image file not found.")

    def write_data_to_image():
        try:
            with PILImage.open(file_path) as img:
                img.load() # Ensure image data is loaded
                
                # Get existing metadata
                metadata = img.info or {}
                
                # Serialize our new user data and add it to the metadata dict
                user_data_json = json.dumps(request.user_data)
                metadata[METADATA_KEY] = user_data_json

                # Create a temporary file to save to, preventing corruption
                temp_path = file_path.with_suffix(f"{file_path.suffix}.tmp")

                # Save the image with the updated metadata
                if img.format == "PNG":
                    png_info = PngImagePlugin.PngInfo()
                    for key, value in metadata.items():
                        png_info.add_text(key, str(value))
                    img.save(temp_path, "PNG", pnginfo=png_info)
                elif img.format == "JPEG":
                    exif_data = img.getexif() # Preserve existing exif
                    img.save(temp_path, "JPEG", quality=95, exif=exif_data, **metadata)
                elif img.format == "WEBP":
                     # WEBP support is more complex, but we can embed simple text
                    exif_bytes = img.info.get("exif", b"")
                    img.save(temp_path, "WEBP", quality=95, exif=exif_bytes, **metadata)
                else:
                    raise HTTPException(status_code=400, detail=f"Unsupported format for metadata writing: {img.format}")

                # If save was successful, atomically replace the original file
                os.replace(temp_path, file_path)
                
                return {"message": "Embedded metadata updated successfully."}
        except Exception as e:
            logger.error(f"Pillow failed to write image data: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to write to image file.")

    return await run_in_threadpool(write_data_to_image)