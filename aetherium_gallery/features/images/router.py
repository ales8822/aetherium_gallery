from __future__ import annotations
import os
import io
import logging
import asyncio
from typing import List, Optional
from pathlib import Path
from PIL import Image as PILImage
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from aetherium_gallery.core.database import get_db
from aetherium_gallery.core.config import settings
from aetherium_gallery import utils
from . import service, models, schemas

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/images",
    tags=["Images API"],
)

upload_router = APIRouter(
    tags=["Image Upload"],
)

@upload_router.post("/upload/single", response_model=schemas.Image, name="handle_single_upload_api")
async def handle_single_upload_api(
    request: Request,
    db: AsyncSession = Depends(get_db),
    file: UploadFile = File(...),
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
    saved_path = None 

    try:
        content = await file.read()
        file_like_object = io.BytesIO(content)
        filename_stem, _, safe_filename = utils.generate_safe_filename(original_filename)

        saved_path = settings.UPLOAD_PATH / safe_filename
        
        with open(saved_path, "wb") as buffer:
            buffer.write(file_like_object.getvalue())
        
        logger.info(f"Successfully saved uploaded file to: {saved_path}")
        
        if content_type.startswith("video/"):
            video_meta, thumbnail_filename = utils.process_video_file(saved_path, filename_stem)
            video_source_obj = await service.create_video_source(db, video_data={
                "filename": safe_filename, "filepath": safe_filename, "content_type": content_type,
                "size_bytes": saved_path.stat().st_size, **video_meta
            })
            image_record_data = {
                "width": video_meta.get('width'), "height": video_meta.get('height'),
                "aspect_ratio": video_meta['width'] / video_meta['height'] if video_meta.get('height', 0) > 0 else 0,
                "video_source_id": video_source_obj.id, "size_bytes": None
            }
        else: 
            utils.generate_thumbnail(saved_path, filename_stem)
            thumbnail_filename = f"thumbnails/{filename_stem}_thumb.webp"
            
            image_meta = utils.parse_metadata_from_image(saved_path)
            form_data = {**image_meta, **{k:v for k,v in form_data.items() if v is not None and v != ''}}
            image_record_data = {
                "width": image_meta.get('width'), "height": image_meta.get('height'),
                "aspect_ratio": image_meta['width'] / image_meta['height'] if image_meta.get('height', 0) > 0 else 0,
                "size_bytes": len(content)
            }
        
        final_image_data = {
            "filename": safe_filename, "original_filename": original_filename,
            "filepath": safe_filename, "thumbnail_path": thumbnail_filename,
            "content_type": content_type, **form_data, **image_record_data
        }
        
        new_image_record = await service.create_image(db, image_data=final_image_data)
        
        vector_service = getattr(request.app.state, "vector_service", None)
        if vector_service and not content_type.startswith("video/") and saved_path.exists():
             logger.info(f"Indexing new image (ID: {new_image_record.id}) for visual search...")
             vector_service.add_image(image_id=new_image_record.id, image_path=saved_path)
        
        logger.info(f"Successfully processed and created entry for: {original_filename}")

    except Exception as e:
        logger.error(f"Upload failed for {original_filename}: {e}", exc_info=True)
        if saved_path and saved_path.exists():
            utils.delete_image_files(saved_path.name, None)
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")
    finally:
        await file.close()

    return new_image_record

@router.get("/", response_model=List[schemas.Image])
async def read_images_api(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    images = await service.get_images(db, skip=skip, limit=limit)
    return images

@router.get("/{image_id}", response_model=schemas.Image)
async def read_image_api(image_id: int, db: AsyncSession = Depends(get_db)):
    db_image = await service.get_image(db, image_id=image_id)
    if db_image is None:
        raise HTTPException(status_code=404, detail="Image not found")
    return db_image

@router.post("/bulk-update", status_code=200)
async def bulk_update_images_api(
    action_request: schemas.BulkActionRequest,
    db: AsyncSession = Depends(get_db)
):
    try:
        affected_count = await service.bulk_update_images(db, action_request)
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
    db_image = await service.get_image(db, image_id=image_id)
    if db_image is None:
        raise HTTPException(status_code=404, detail="Image not found")
    updated_image = await service.update_image(db=db, db_image=db_image, image_update=image_update)
    return updated_image

@router.delete("/{image_id}", status_code=204, name="delete_image_api")
@router.post("/delete/{image_id}", response_class=RedirectResponse, status_code=303, name="delete_image_api_post")
async def delete_image_api(image_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    db_image = await service.get_image(db, image_id)
    if db_image is None:
        raise HTTPException(status_code=404, detail="Image not found")

    files_deleted = utils.delete_image_files(db_image.filename, db_image.thumbnail_path)
    if not files_deleted:
            logger.warning(f"Could not delete files for image ID {image_id}. Proceeding with DB deletion.")

    deleted_record = await service.delete_image(db, image_id=image_id)
    if deleted_record is None:
            raise HTTPException(status_code=404, detail="Image found initially but failed to delete from DB")

    gallery_url = request.url_for('gallery_index')
    return RedirectResponse(url=gallery_url, status_code=303)
