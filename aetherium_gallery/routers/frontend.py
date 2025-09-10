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
    # Read the new media filter cookie, defaulting to 'all'
    media_filter = request.cookies.get("media_filter", "all")

    # Pass the flag to the CRUD function
    images = await crud.get_images(db, skip=skip, limit=limit, safe_mode=safe_mode_enabled,  media_type=media_filter )
    albums_with_counts = await crud.get_all_albums(db)
    albums = [album for album, count in albums_with_counts]

    return templates.TemplateResponse("index.html", {
        "request": request,
        "images": images,
        "albums": albums,
        "upload_folder": f"/{settings.UPLOAD_FOLDER}",
        "page_title": "Aetherium Gallery",
        "now": datetime.datetime.now,
        "safe_mode": safe_mode_enabled,
        "media_filter": media_filter, 
    })

@router.get("/upload", response_class=HTMLResponse, name="upload_form")
async def show_upload_form(request: Request, db: AsyncSession = Depends(get_db)):
    """Serves the image upload form page."""
    # Fetch all albums to populate the dropdown
    albums_with_counts = await crud.get_all_albums(db)
    # Extract just the album objects from the tuples
    albums = [album for album, count in albums_with_counts]
    return templates.TemplateResponse("upload.html", {
        "request": request,
         "albums": albums,
        "page_title": "Upload Image",
        "now": datetime.datetime.now, # Pass it here as well if your upload form uses the footer
    })

@router.get("/image/{image_id}", response_class=HTMLResponse, name="image_detail")
async def read_image_detail(request: Request, image_id: int, db: AsyncSession = Depends(get_db)):
    """Serves the page for a single image view."""
    db_image = await crud.get_image(db, image_id=image_id)
    if db_image is None:
        raise HTTPException(status_code=404, detail="Image not found")
    # Fetch all albums to populate the editor's dropdown menu
    all_albums_with_counts = await crud.get_all_albums(db)
    all_albums = [album for album, count in all_albums_with_counts]

     # Fetch related images based on the current image's tags
    related_images = await crud.get_related_images(db, source_image=db_image, limit=10)

    return templates.TemplateResponse("image_detail.html", {
        "request": request,
        "image": db_image, # Pass ORM model directly
        "all_albums": all_albums,
        "related_images": related_images,
        "upload_folder": f"/{settings.UPLOAD_FOLDER}", # Access UPLOAD_FOLDER from the settings instance
        "page_title": f"Image - {db_image.original_filename or db_image.filename}",
        "now": datetime.datetime.now, # Pass it here too
    })

@router.get("/search", response_class=HTMLResponse, name="search")
async def search_results(
    request: Request,
    db: AsyncSession = Depends(get_db),
    q: Optional[str] = Query(None, min_length=2, max_length=100)
):
    """Displays search results based on a query."""
    safe_mode_enabled = request.cookies.get("safe_mode", "off") == "on"
    media_filter = request.cookies.get("media_filter", "all")
    
    # Always fetch albums
    albums_with_counts = await crud.get_all_albums(db)
    albums = [album for album, count in albums_with_counts]
    
    images = []
    if q:
        # Pass the media_filter to the search function
        images = await crud.search_images(
            db, query=q, safe_mode=safe_mode_enabled, media_type=media_filter, limit=100
        )

    return templates.TemplateResponse("search_results.html", {
        "request": request,
        "images": images,
        "albums": albums, # Pass the correct, always-defined variable
        "image_count": len(images),
        "search_query": q,
        "page_title": f"Search results for '{q}'",
        "now": datetime.datetime.now,
        "safe_mode": safe_mode_enabled,
        "media_filter": media_filter
    })

@router.get("/tag/{tag_name}", response_class=HTMLResponse, name="tag_gallery")
async def read_images_by_tag(
    request: Request,
    tag_name: str,
    db: AsyncSession = Depends(get_db)
):
    """Displays a gallery of all images for a specific tag."""
    safe_mode_enabled = request.cookies.get("safe_mode", "off") == "on"

    # Use the CRUD function we already built to fetch the images
    images = await crud.get_images_by_tag(
        db, tag_name=tag_name, safe_mode=safe_mode_enabled, limit=100
    )
    albums_with_counts = await crud.get_all_albums(db)
    albums = [album for album, count in albums_with_counts]

    return templates.TemplateResponse("tag_gallery.html", {
        "request": request,
        "images": images,
        "albums": albums,
        "image_count": len(images),
        "tag_name": tag_name,
        "page_title": f"Tag: {tag_name}",
        "now": datetime.datetime.now,
        "safe_mode": safe_mode_enabled,
    })
# Add routes for viewing/managing tags and albums later