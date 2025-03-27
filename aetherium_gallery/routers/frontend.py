# aetherium_gallery/routers/frontend.py
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
import os
import datetime  # Import the datetime module

from .. import crud, schemas
from ..database import get_db
from ..config import BASE_DIR, settings

router = APIRouter()

# Configure Jinja2 templates
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

@router.get("/", response_class=HTMLResponse, name="gallery_index")
async def read_gallery_index(request: Request, db: AsyncSession = Depends(get_db), skip: int = 0, limit: int = 50):
    """Serves the main gallery page."""
    images = await crud.get_images(db, skip=skip, limit=limit)
    # Convert model instances to schemas suitable for template, or pass models directly if template handles it
    # image_schemas = [schemas.Image.from_orm(img) for img in images]
    return templates.TemplateResponse("index.html", {
        "request": request,
        "images": images, # Pass the ORM models directly
        "upload_folder": f"/{settings.UPLOAD_FOLDER}", # Access UPLOAD_FOLDER from the settings instance
        "page_title": "Aetherium Gallery",
        "now": datetime.datetime.now, # Pass the datetime.datetime.now function
    })

@router.get("/upload", response_class=HTMLResponse, name="upload_form")
async def show_upload_form(request: Request):
    """Serves the image upload form page."""
    return templates.TemplateResponse("upload.html", {
        "request": request,
        "page_title": "Upload Image",
        "now": datetime.datetime.now, # Pass it here as well if your upload form uses the footer
    })

@router.get("/image/{image_id}", response_class=HTMLResponse, name="image_detail")
async def read_image_detail(request: Request, image_id: int, db: AsyncSession = Depends(get_db)):
    """Serves the page for a single image view."""
    db_image = await crud.get_image(db, image_id=image_id)
    if db_image is None:
        raise HTTPException(status_code=404, detail="Image not found")
    # image_schema = schemas.Image.from_orm(db_image)
    return templates.TemplateResponse("image_detail.html", {
        "request": request,
        "image": db_image, # Pass ORM model directly
        "upload_folder": f"/{settings.UPLOAD_FOLDER}", # Access UPLOAD_FOLDER from the settings instance
        "page_title": f"Image - {db_image.original_filename or db_image.filename}",
        "now": datetime.datetime.now, # Pass it here too
    })

# Add routes for viewing/managing tags and albums later