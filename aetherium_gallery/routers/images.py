import shutil
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import logging

from .. import crud, models, schemas, utils
from ..database import get_db
from ..config import settings
from pathlib import Path

router = APIRouter(
    prefix="/api/images", # Prefix for API-specific routes
    tags=["Images API"],   # Tag for API documentation
)

upload_router = APIRouter(
        tags=["Image Upload"], # Separate tag for the user-facing upload endpoint
)

logger = logging.getLogger(__name__)

# --- User-Facing Upload Endpoint (part of the web UI flow) ---

@upload_router.post("/upload", response_class=RedirectResponse, name="handle_upload")
async def handle_image_upload(
    request: Request, # Needed for URL generation
    files: List[UploadFile] = File(..., description="Images to upload"),
    db: AsyncSession = Depends(get_db)
):
    """Handles image uploads from the web form."""
    processed_count = 0
    error_count = 0

    if not files:
        # Redirect back with an error message? Or handle in frontend JS
        raise HTTPException(status_code=400, detail="No files were uploaded.")

    for file in files:
        if not file.content_type or not file.content_type.startswith("image/"):
            logger.warning(f"Skipping non-image file: {file.filename} ({file.content_type})")
            error_count += 1
            continue # Skip non-image files

        original_filename = file.filename
        logger.info(f"Processing uploaded file: {original_filename}")

        try:
            # 1. Generate unique filename & save
            filename_stem, extension, safe_filename = utils.generate_safe_filename(original_filename)
            saved_path = utils.save_uploaded_image(file, safe_filename)

            # 2. Generate Thumbnail
            thumbnail_filename = utils.generate_thumbnail(saved_path, filename_stem, extension)

            # 3. Parse Metadata (Basic)
            metadata = utils.parse_metadata_from_image(saved_path)

            # 4. Prepare data for DB record
            image_data = {
                "filename": safe_filename,
                "original_filename": original_filename,
                "filepath": safe_filename, # Store relative path/filename
                "thumbnail_path": thumbnail_filename, # Store relative path/filename
                "content_type": file.content_type,
                "size_bytes": saved_path.stat().st_size if saved_path.exists() else None,
                # Add parsed metadata:
                **metadata # Unpack the dict, only keys matching model fields will be used
            }

            # 5. Create DB Record
            await crud.create_image(db=db, image_data=image_data)
            processed_count += 1
            logger.info(f"Successfully processed and saved: {original_filename} as {safe_filename}")

        except Exception as e:
            logger.error(f"Failed to process file {original_filename}: {e}", exc_info=True)
            error_count += 1
            # Consider cleanup of partially saved files if needed

        finally:
            # Ensure the file descriptor is closed
            await file.close()


    # Redirect back to the gallery index after processing all files
    # Optionally add query params for success/error messages
    # status_message = f"Processed: {processed_count}, Errors: {error_count}"
    gallery_url = request.url_for('gallery_index')
    return RedirectResponse(url=gallery_url, status_code=303) # Use 303 See Other for POST redirect


# --- API Endpoints (Example: could be used by a JavaScript frontend later) ---

@router.get("/", response_model=List[schemas.Image])
async def read_images_api(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    """API endpoint to retrieve a list of images."""
    images = await crud.get_images(db, skip=skip, limit=limit)
    return images

@router.get("/{image_id}", response_model=schemas.Image)
async def read_image_api(image_id: int, db: AsyncSession = Depends(get_db)):
    """API endpoint to retrieve a single image by ID."""
    db_image = await crud.get_image(db, image_id=image_id)
    if db_image is None:
        raise HTTPException(status_code=404, detail="Image not found")
    return db_image

@router.patch("/{image_id}", response_model=schemas.Image)
async def update_image_api(
    image_id: int,
    image_update: schemas.ImageUpdate,
    db: AsyncSession = Depends(get_db)
):
    """API endpoint to update image metadata (e.g., rating, notes)."""
    db_image = await crud.get_image(db, image_id=image_id)
    if db_image is None:
        raise HTTPException(status_code=404, detail="Image not found")
    updated_image = await crud.update_image(db=db, db_image=db_image, image_update=image_update)
    return updated_image

@router.delete("/{image_id}", status_code=204, name="delete_image_api")
@router.post("/delete/{image_id}", response_class=RedirectResponse, status_code=303, name="delete_image_api_post")
async def delete_image_api(image_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    """API endpoint to delete an image."""
    db_image = await crud.get_image(db, image_id) # Fetch before deleting to get filenames
    if db_image is None:
        raise HTTPException(status_code=404, detail="Image not found")

    # First, delete files from storage
    files_deleted = utils.delete_image_files(db_image.filename, db_image.thumbnail_path)
    if not files_deleted:
            # Log a warning, but proceed to delete DB record anyway? Or raise error?
            logger.warning(f"Could not delete files for image ID {image_id}. Proceeding with DB deletion.")

    # Then, delete the database record
    deleted_record = await crud.delete_image(db, image_id=image_id)
    if deleted_record is None:
            # This shouldn't happen if we found it above, but handle defensively
            raise HTTPException(status_code=404, detail="Image found initially but failed to delete from DB")

    # Redirect back to the gallery
    gallery_url = request.url_for('gallery_index')
    return RedirectResponse(url=gallery_url, status_code=303) # Use 303 See Other for POST redirect