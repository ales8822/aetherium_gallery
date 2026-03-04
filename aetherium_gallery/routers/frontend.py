# aetherium_gallery/routers/frontend.py

from typing import Optional, List
from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
import datetime

# --- NEW ARCHITECTURE IMPORTS ---
from ..core.database import get_db
from ..core.config import settings, BASE_DIR

# Import Services from Features
from ..features.images import service as image_service
from ..features.albums import service as album_service
# If you have a tag service, import it here. 
# For now, I'll assume tag logic might still be in image_service or needs a direct query.

router = APIRouter()

# Configure Jinja2 templates
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

@router.get("/", response_class=HTMLResponse, name="gallery_index")
async def read_gallery_index(
    request: Request, db: AsyncSession = Depends(get_db), skip: int = 0, limit: int = 50
):
    """Serves the main gallery page."""
    safe_mode_enabled = request.cookies.get("safe_mode", "off") == "on"
    media_filter = request.cookies.get("media_filter", "all")

    # UDPATE: Use image_service
    images = await image_service.get_images(
        db, skip=skip, limit=limit, safe_mode=safe_mode_enabled, media_type=media_filter
    )
    
    # UPDATE: Use album_service
    albums_with_counts = await album_service.get_all_albums(db)
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
    # UPDATE: Use album_service
    albums_with_counts = await album_service.get_all_albums(db)
    albums = [album for album, count in albums_with_counts]
    
    return templates.TemplateResponse("upload.html", {
        "request": request,
        "albums": albums,
        "page_title": "Upload Image",
        "now": datetime.datetime.now,
    })

@router.get("/image/{image_id}", response_class=HTMLResponse, name="image_detail")
async def read_image_detail(request: Request, image_id: int, db: AsyncSession = Depends(get_db)):
    """Serves the page for a single image view."""
    # UPDATE: Use image_service
    db_image = await image_service.get_image(db, image_id=image_id)
    if db_image is None:
        raise HTTPException(status_code=404, detail="Image not found")
    
    # UPDATE: Use album_service
    all_albums_with_counts = await album_service.get_all_albums(db)
    all_albums = [album for album, count in all_albums_with_counts]

    # UPDATE: Use image_service for related images
    related_images = await image_service.get_related_images(db, source_image=db_image, limit=10)

    return templates.TemplateResponse("image_detail.html", {
        "request": request,
        "image": db_image,
        "all_albums": all_albums,
        "related_images": related_images,
        "upload_folder": f"/{settings.UPLOAD_FOLDER}",
        "page_title": f"Image - {db_image.original_filename or db_image.filename}",
        "now": datetime.datetime.now,
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
    
    # UPDATE: Use album_service
    albums_with_counts = await album_service.get_all_albums(db)
    albums = [album for album, count in albums_with_counts]
    
    images = []
    if q:
        # UPDATE: Use image_service.search_images
        images = await image_service.search_images(
            db, query=q, safe_mode=safe_mode_enabled, media_type=media_filter, limit=100
        )

    return templates.TemplateResponse("search_results.html", {
        "request": request,
        "images": images,
        "albums": albums,
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

    # UPDATE: Use image_service.get_images_by_tag
    images = await image_service.get_images_by_tag(
        db, tag_name=tag_name, safe_mode=safe_mode_enabled, limit=100
    )
    
    # UPDATE: Use album_service
    albums_with_counts = await album_service.get_all_albums(db)
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

@router.get("/similar/{image_id}", response_class=HTMLResponse, name="find_similar")
async def show_similar_images(
    request: Request,
    image_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Displays a gallery of images that are visually similar."""
    # UPDATE: Use image_service
    source_image = await image_service.get_image(db, image_id=image_id)
    if not source_image:
        raise HTTPException(status_code=404, detail="Source image not found")

    if source_image.video_source or not source_image.thumbnail_path:
        raise HTTPException(
            status_code=400, 
            detail="Similarity search is not applicable for videos or images with missing thumbnails."
        )

    vector_service = request.app.state.vector_service
    
    similar_images = []
    if vector_service and not source_image.video_source:
        # Note: We access settings from the new location
        source_image_path = settings.UPLOAD_PATH / source_image.filename
        
        if source_image_path.exists():
            similar_ids = vector_service.find_similar_images_by_path(
                image_path=source_image_path,
                source_id=source_image.id,
                n_results=12
            )
            
            if similar_ids:
                # UPDATE: Use image_service
                db_images = await image_service.get_images_by_ids(db, image_ids=similar_ids)
                id_map = {img.id: img for img in db_images}
                similar_images = [id_map[id] for id in similar_ids if id in id_map]

    # UPDATE: Use album_service
    albums_with_counts = await album_service.get_all_albums(db)
    albums = [album for album, count in albums_with_counts]
    
    return templates.TemplateResponse("similar_results.html", {
        "request": request,
        "source_image": source_image,
        "images": similar_images,
        "image_count": len(similar_images),
        "albums": albums,
        "page_title": f"Images similar to '{source_image.original_filename}'",
        "now": datetime.datetime.now,
        "safe_mode": request.cookies.get("safe_mode", "off") == "on"
    })

@router.get("/map", response_class=HTMLResponse, name="constellation_map")
async def show_constellation_map(request: Request):
    """Serves the Constellation Map visualization page."""
    return templates.TemplateResponse("constellation_map.html", {
        "request": request,
        "page_title": "Constellation Map",
        "now": datetime.datetime.now,
    })


@router.get("/gallery-chunk", response_class=HTMLResponse, name="gallery_chunk")
async def get_gallery_chunk(
    request: Request, db: AsyncSession = Depends(get_db), skip: int = 0, limit: int = 50
):
    """
    Returns just the HTML grid partial for infinite scrolling.
    Called by JavaScript via AJAX.
    """
    safe_mode_enabled = request.cookies.get("safe_mode", "off") == "on"
    media_filter = request.cookies.get("media_filter", "all")

    images = await image_service.get_images(
        db, skip=skip, limit=limit, safe_mode=safe_mode_enabled, media_type=media_filter
    )
    
    # We render ONLY the partial template, not the full base.html
    return templates.TemplateResponse("partials/gallery_grid.html", {
        "request": request,
        "images": images,
        "upload_folder": f"/{settings.UPLOAD_FOLDER}",
        # We don't need albums or page_title here because it's just a fragment
    })