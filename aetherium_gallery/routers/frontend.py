# aetherium_gallery/routers/frontend.py
from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException, Query
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
async def read_gallery_index(
    request: Request, db: AsyncSession = Depends(get_db), skip: int = 0, limit: int = 50
):
    """Serves the main gallery page."""
    # Check for the 'safe_mode' cookie from the user's browser
    safe_mode_enabled = request.cookies.get("safe_mode", "off") == "on"

    # Pass the flag to the CRUD function
    images = await crud.get_images(db, skip=skip, limit=limit, safe_mode=safe_mode_enabled)
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "images": images,
        "upload_folder": f"/{settings.UPLOAD_FOLDER}",
        "page_title": "Aetherium Gallery",
        "now": datetime.datetime.now,
        "safe_mode": safe_mode_enabled # Pass the status to the template
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

@router.get("/search", response_class=HTMLResponse, name="search")
async def search_results(
    request: Request,
    db: AsyncSession = Depends(get_db),
    # Use Query() for better validation and documentation
    q: Optional[str] = Query(None, min_length=2, max_length=100)
):
    """Displays search results based on a query."""
    safe_mode_enabled = request.cookies.get("safe_mode", "off") == "on"
    
    images = []
    if q:
        # Call our new CRUD function
        images = await crud.search_images(db, query=q, safe_mode=safe_mode_enabled, limit=100)

    return templates.TemplateResponse("search_results.html", {
        "request": request,
        "images": images,
        "image_count": len(images),
        "search_query": q,
        "page_title": f"Search results for '{q}'",
        "now": datetime.datetime.now,
        "safe_mode": safe_mode_enabled,
    })

# Add routes for viewing/managing tags and albums later