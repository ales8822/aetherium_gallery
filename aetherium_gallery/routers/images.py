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
async def handle_staged_upload(
    request: Request,
    db: AsyncSession = Depends(get_db),
    file: UploadFile = File(...),
    original_filename: str = Form(...),
    prompt: Optional[str] = Form(None),
    negative_prompt: Optional[str] = Form(None),
    steps: Optional[str] = Form(None),
    sampler: Optional[str] = Form(None),
    cfg_scale: Optional[str] = Form(None),
    seed: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    is_nsfw: Optional[str] = Form(None), 
    tags: Optional[str] = Form(None),
    album_id: Optional[str] = Form(None)
):
    """
    Handles a staged upload of a single file, which can be an IMAGE or a VIDEO.
    """
    content_type = file.content_type
    if not (content_type.startswith("image/") or content_type.startswith("video/")):
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {content_type}")

    logger.info(f"Processing staged upload for '{original_filename}' of type '{content_type}'")
    
    # --- Prepare common data (from form) ---
    filename_stem, extension, safe_filename = utils.generate_safe_filename(original_filename)
    
    # Safely convert form data
    try:
        steps_int = int(steps) if steps and steps.isdigit() else None
        cfg_float = float(cfg_scale) if cfg_scale else None
        seed_int = int(seed) if seed and seed.isdigit() else None
        album_id_int = int(album_id) if album_id and album_id.isdigit() else None
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid numeric form data provided.")
        
    is_nsfw_bool = (is_nsfw == 'on')

    # This will hold the final data to be saved in the Image table
    image_data = {}

    try:
        # --- Handle VIDEO Files ---
        if content_type.startswith("video/"):
            # 1. Save video file to disk first
            video_path = utils.save_uploaded_file(file.file, safe_filename)

            # 2. Process video: get metadata and generate a thumbnail
            video_meta, thumbnail_filename = utils.process_video_file(video_path, filename_stem)

            # 3. Create the VideoSource DB record
            video_source_data = {
                "filename": safe_filename,
                "filepath": safe_filename,
                "content_type": content_type,
                "size_bytes": video_path.stat().st_size,
                **video_meta # Unpack width, height, duration
            }
            video_source_obj = await crud.create_video_source(db, video_data=video_source_data)
            
            # 4. Prepare data for the main Image record
            image_data = {
                "width": video_meta.get('width'),
                "height": video_meta.get('height'),
                "aspect_ratio": video_meta.get('width') / video_meta.get('height') if video_meta.get('height') > 0 else 0,
                "video_source_id": video_source_obj.id, # Link to the video source!
            }
            
        # --- Handle IMAGE Files ---
        else: # Assumed image/
            content = await file.read()
            file_bytes_io = io.BytesIO(content)

            saved_path = utils.save_uploaded_file(file_bytes_io, safe_filename)
            file_bytes_io.seek(0)
            thumbnail_filename = utils.generate_thumbnail(file_bytes_io, filename_stem, ".jpg") # Standardize thumb extension

            image_meta = utils.parse_metadata_from_image(saved_path)
            
            image_data = {
                "width": image_meta.get('width'),
                "height": image_meta.get('height'),
                "aspect_ratio": image_meta.get('width') / image_meta.get('height') if image_meta.get('height', 0) > 0 else 0,
                "size_bytes": len(content),
            }

        # --- Populate and Save the final Image record ---
        final_image_data = {
            "filename": safe_filename,
            "original_filename": original_filename,
            "filepath": safe_filename,
            "thumbnail_path": thumbnail_filename,
            "content_type": content_type,
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "sampler": sampler,
            "notes": notes,
            "steps": steps_int,
            "cfg_scale": cfg_float,
            "seed": seed_int,
            "is_nsfw": is_nsfw_bool,
            "tags": tags,
            "album_id": album_id_int,
            **image_data # Add the image/video specific data
        }
        
        await crud.create_image(db, image_data=final_image_data)
        logger.info(f"Successfully processed and created entry for: {original_filename}")

    except Exception as e:
        logger.error(f"Failed to process file {original_filename}: {e}", exc_info=True)
        # We should ideally show an error message to the user here
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")
    finally:
        await file.close()

    return RedirectResponse(url=request.url_for('gallery_index'), status_code=303)

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

def process_video_file(video_path: Path, filename_stem: str) -> (dict, str):
    """
    Uses FFmpeg to extract metadata and a thumbnail from a video.
    Returns a dictionary of metadata and the thumbnail filename.
    """
    logger.info(f"Processing video file: {video_path}")
    thumbnail_filename = f"{filename_stem}_thumb.jpg" # Always save video thumbs as jpg
    thumbnail_filepath = settings.UPLOAD_PATH / thumbnail_filename
    
    try:
        # Probe for video metadata
        probe = ffmpeg.probe(str(video_path))
        video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
        if video_stream is None:
            raise RuntimeError("No video stream found in the file.")

        metadata = {
            "width": int(video_stream['width']),
            "height": int(video_stream['height']),
            "duration": float(video_stream['duration']),
        }
        
        # Extract the first frame as a thumbnail
        (
            ffmpeg
            .input(str(video_path), ss=0) # Seek to the beginning
            .output(str(thumbnail_filepath), vframes=1) # Output one frame
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        logger.info(f"Generated video thumbnail: {thumbnail_filepath}")
        
        return metadata, thumbnail_filename
        
    except ffmpeg.Error as e:
        logger.error(f"FFmpeg error processing {video_path}: {e.stderr.decode()}")
        raise  # Re-raise the exception to be handled by the route
    except Exception as e:
        logger.error(f"General error processing video {video_path}: {e}")
        raise