import shutil
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import logging
from fastapi import File, Form, UploadFile
from PIL import Image as PILImage # Use an alias to avoid name conflicts
import json
import io
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

@upload_router.post("/upload-staged", response_class=RedirectResponse, name="handle_staged_upload")
async def handle_staged_image_upload(
    request: Request,
    db: AsyncSession = Depends(get_db),
    file: UploadFile = File(...),
    original_filename: str = Form(...),
    prompt: Optional[str] = Form(None),
    negative_prompt: Optional[str] = Form(None),
    # ▼▼▼ CHANGE 1: Accept problematic fields as Optional[str] ▼▼▼
    steps: Optional[str] = Form(None),
    sampler: Optional[str] = Form(None),
    cfg_scale: Optional[str] = Form(None),
    seed: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    # This will be 'on' if checked, and None if not. We default it to False.
    is_nsfw: Optional[str] = Form(None), 
    tags: Optional[str] = Form(None),
    album_id: Optional[str] = Form(None)
):
    """
    Handles the submission from the new advanced upload form with a single
    image and its potentially user-edited metadata.
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid image.")

    logger.info(f"Processing staged upload: {original_filename}")
    try:
        # We read the file content into memory once to be used by multiple functions
        content = await file.read()
        file_bytes_io = io.BytesIO(content)

        # 1. Generate unique filename
        filename_stem, extension, safe_filename = utils.generate_safe_filename(original_filename)

        # 2. Save the image from the in-memory bytes
        saved_path = utils.save_uploaded_image(file_bytes_io, safe_filename)

        # 3. Generate a thumbnail from the in-memory bytes
        file_bytes_io.seek(0) # Reset the "cursor" of the in-memory file
        thumbnail_filename = utils.generate_thumbnail(file_bytes_io, filename_stem, extension)
        
        # 4. Get image dimensions (re-opening the saved file is most reliable)
        with PILImage.open(saved_path) as img:
            width, height = img.size
            
        # ▼▼▼ CHANGE 2: Manually convert the string values to numbers inside the function ▼▼▼
        # This gives us full control over empty strings.
        try:
            steps_int = int(steps) if steps else None
        except (ValueError, TypeError):
            steps_int = None
            
        try:
            cfg_float = float(cfg_scale) if cfg_scale else None
        except (ValueError, TypeError):
            cfg_float = None

        try:
            seed_int = int(seed) if seed and seed.isdigit() else None
        except (ValueError, TypeError):
            seed_int = None

        try:
            album_id_int = int(album_id) if album_id else None
        except (ValueError, TypeError):
            album_id_int = None

        # This converts the 'on' from the checkbox to a boolean True/False
        is_nsfw_bool = (is_nsfw == 'on')

        # 5. Prepare data for DB record USING THE FORM DATA
        image_data = {
            "filename": safe_filename,
            "original_filename": original_filename,
            "filepath": safe_filename,
            "thumbnail_path": thumbnail_filename,
            "content_type": file.content_type,
            "size_bytes": len(content),
            "width": width,
            "height": height,
            # Use the data from the form fields
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "sampler": sampler,
            "notes": notes,
            # Use our safely converted values
            "steps": steps_int,
            "cfg_scale": cfg_float,
            "seed": seed_int,
            "is_nsfw": is_nsfw_bool,
            "tags": tags,
            "album_id": album_id_int
        }

        # 6. Create the database record
        await crud.create_image(db=db, image_data=image_data)
        logger.info(f"Successfully processed staged upload: {original_filename} as {safe_filename}")

    except Exception as e:
        logger.error(f"Failed to process staged file {original_filename}: {e}", exc_info=True)
    finally:
        await file.close()

    gallery_url = request.url_for('gallery_index')
    return RedirectResponse(url=gallery_url, status_code=303)


@router.post("/extract-metadata", summary="Extract metadata from an uploaded image")
async def extract_metadata_from_image(file: UploadFile = File(...)):
    """
    Accepts an image file, extracts metadata using Pillow, and returns it.
    This does not save the image or create any database records.
    """
    # This logic can be moved to a `utils.py` function if you prefer
    try:
        # Since Pillow might need to re-read the stream, we load it into memory
        content = await file.read()
        image = PILImage.open(io.BytesIO(content))
        
        extracted_data = utils.parse_metadata_from_image(io.BytesIO(content))

        # We also want to include dimensions
        width, height = image.size
        extracted_data["width"] = width
        extracted_data["height"] = height
        
        return extracted_data

    except Exception as e:
        logger.error(f"Pillow failed to process image metadata: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to process image metadata: {str(e)}")


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



@router.post("/bulk-update", status_code=200)
async def bulk_update_images_api(
    action_request: schemas.BulkActionRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Performs a bulk action (e.g., add tags, set NSFW, delete)
    on a list of specified image IDs.
    """
    try:
        # Pass the 'utils' module to the CRUD function so it can call delete_image_files
        affected_count = await crud.bulk_update_images(db, action_request, utils_module=utils)
        return {
            "message": f"Action '{action_request.action}' performed successfully.",
            "images_affected": affected_count
        }
    except Exception as e:
        logger.error(f"Bulk update failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred during the bulk update.")
        

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