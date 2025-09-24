import shutil
import os
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Form, Request
from fastapi.responses import RedirectResponse, JSONResponse
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
import asyncio


router = APIRouter(
    prefix="/api/images", # Prefix for API-specific routes
    tags=["Images API"],   # Tag for API documentation
)

upload_router = APIRouter(
        tags=["Image Upload"], # Separate tag for the user-facing upload endpoint
)

logger = logging.getLogger(__name__)

# --- User-Facing Upload Endpoint (part of the web UI flow) ---

@upload_router.post("/upload/single", response_model=schemas.Image, name="handle_single_upload_api")
async def handle_single_upload_api(
    request: Request,
    db: AsyncSession = Depends(get_db),
    file: UploadFile = File(...),
    # ... all other form fields ...
    original_filename: str = Form(...),
    prompt: Optional[str] = Form(None), negative_prompt: Optional[str] = Form(None),
    steps: Optional[str] = Form(None), sampler: Optional[str] = Form(None),
    cfg_scale: Optional[str] = Form(None), seed: Optional[str] = Form(None),
    notes: Optional[str] = Form(None), is_nsfw: Optional[str] = Form(None),
    tags: Optional[str] = Form(None), album_id: Optional[str] = Form(None),
 
):
    content_type = file.content_type
    if not (content_type and (content_type.startswith("image/") or content_type.startswith("video/"))):
        raise HTTPException(status_code=400, detail="Unsupported file type.")

    logger.info(f"Processing '{original_filename}'...")

    form_data = {
        "prompt": prompt, "negative_prompt": negative_prompt, "sampler": sampler, "notes": notes,
        "tags": tags, "is_nsfw": (is_nsfw == 'on'),
        "steps": int(steps) if steps and steps.isdigit() else None,
        "cfg_scale": float(cfg_scale) if cfg_scale else None,
        "seed": int(seed) if seed and seed.isdigit() else None,
        "album_id": int(album_id) if album_id and album_id.isdigit() else None,
    }

    image_record_data = {}
    thumbnail_filename = ""
    saved_path = None # Will hold the final Path object of the saved file

    try:
        content = await file.read()
        file_like_object = io.BytesIO(content)
        filename_stem, _, safe_filename = utils.generate_safe_filename(original_filename)

        # The 'saved_path' variable will now be the definitive location of the final file on disk.
        saved_path = utils.settings.UPLOAD_PATH / safe_filename
        
        # We save the file using a different utility that works directly with bytes
        with open(saved_path, "wb") as buffer:
            buffer.write(file_like_object.getvalue())
        
        logger.info(f"Successfully saved uploaded file to: {saved_path}")
        

        # Process Video or Image from the definitive saved_path
        if content_type.startswith("video/"):
            # This part is likely working correctly, so we leave it as is.
            video_meta, thumbnail_filename = utils.process_video_file(saved_path, filename_stem)
            video_source_obj = await crud.create_video_source(db, video_data={
                "filename": safe_filename, "filepath": safe_filename, "content_type": content_type,
                "size_bytes": saved_path.stat().st_size, **video_meta
            })
            image_record_data = {
                "width": video_meta.get('width'), "height": video_meta.get('height'),
                "aspect_ratio": video_meta['width'] / video_meta['height'] if video_meta.get('height', 0) > 0 else 0,
                "video_source_id": video_source_obj.id, "size_bytes": None
            }
        else: # Handle Image
            # ▼▼▼ THIS BLOCK IS THE FIX ▼▼▼

            # 1. Call the utility to create the thumbnail file on disk. We ignore its return value.
            utils.generate_thumbnail(saved_path, filename_stem)

            # 2. Explicitly construct the relative path that MUST be saved to the database.
            #    This ensures the path is correct regardless of what the utility returns.
            thumbnail_filename = f"thumbnails/{filename_stem}_thumb.webp"
            
            # This part of the logic remains the same
            image_meta = utils.parse_metadata_from_image(saved_path)
            form_data = {**image_meta, **{k:v for k,v in form_data.items() if v is not None and v != ''}}
            image_record_data = {
                "width": image_meta.get('width'), "height": image_meta.get('height'),
                "aspect_ratio": image_meta['width'] / image_meta['height'] if image_meta.get('height', 0) > 0 else 0,
                "size_bytes": len(content)
            }
        
        # Create final DB record (This part now receives the correct thumbnail_path)
        final_image_data = {
            "filename": safe_filename, "original_filename": original_filename,
            "filepath": safe_filename, "thumbnail_path": thumbnail_filename,
            "content_type": content_type, **form_data, **image_record_data
        }
        
        new_image_record = await crud.create_image(db, image_data=final_image_data)
        
        # --- Indexing for Visual Search ---
        vector_service = request.app.state.vector_service
        if vector_service and not content_type.startswith("video/") and saved_path.exists():
             logger.info(f"Indexing new image (ID: {new_image_record.id}) for visual search...")
             # Pass the definitive, final path on disk.
             vector_service.add_image(image_id=new_image_record.id, image_path=saved_path)
        
        logger.info(f"Successfully processed and created entry for: {original_filename}")

    except Exception as e:
        logger.error(f"Upload failed for {original_filename}: {e}", exc_info=True)
        # Clean up partially saved file if something went wrong
        if saved_path and saved_path.exists():
            utils.delete_image_files(saved_path.name, None)
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")
    finally:
        await file.close()

    return new_image_record

@router.post("/extract-metadata", summary="Extract metadata from an uploaded image")
async def extract_metadata_from_image(file: UploadFile = File(...)):
    """
    Accepts an image file, extracts metadata using Pillow, and returns it.
    This does not save the image or create any database records.
    """
     # Only images have extractable metadata for now
    if not file.content_type.startswith("image/"):
        return {"prompt": "", "notes": "Metadata extraction is only available for images."}
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



def save_uploaded_file(file, filename: str) -> Path:
    """
    Saves any uploaded file (image or video) content to the designated path.
    Handles both FastAPI UploadFile objects and in-memory BytesIO objects.
    """
    file_path = settings.UPLOAD_PATH / filename
    try:
        if hasattr(file, 'file'):
            # It's an UploadFile, reset cursor and read
            file.file.seek(0)
            content = file.file.read()
        else:
            # It's a file-like object (BytesIO), reset cursor and read
            file.seek(0)
            content = file.read()

        with open(file_path, "wb") as buffer:
            buffer.write(content)
        
        logger.info(f"Saved uploaded file to: {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"Error saving file {filename}: {e}", exc_info=True)
        # Clean up partial file on error
        if file_path.exists():
            try:
                os.remove(file_path)
            except OSError:
                pass
        raise

