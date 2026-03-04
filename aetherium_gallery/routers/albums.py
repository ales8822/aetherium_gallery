# aetherium_gallery/routers/albums.py

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
import datetime

# --- NEW ARCHITECTURE IMPORTS ---
from ..core.database import get_db
from ..core.config import BASE_DIR

# Import Feature Components
from ..features.albums import service as album_service
from ..features.albums import schemas as album_schemas

router = APIRouter(
    tags=["Albums Frontend"],
)

# Use the same templates instance from your frontend router
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

@router.get("/albums", response_class=HTMLResponse, name="list_albums")
async def list_all_albums(request: Request, db: AsyncSession = Depends(get_db)):
    """Serves the page that lists all created albums."""
    # The Service function returns a list of (album, image_count) tuples
    albums_with_counts = await album_service.get_all_albums(db)
    
    return templates.TemplateResponse("albums/album_list.html", {
        "request": request,
        "albums_with_counts": albums_with_counts,
        "page_title": "All Albums",
        "now": datetime.datetime.now,
    })
    
@router.get("/album/{album_id}", response_class=HTMLResponse, name="view_album")
async def view_album_contents(request: Request, album_id: int, db: AsyncSession = Depends(get_db)):
    """Serves the gallery page for a single album."""
    result = await album_service.get_album(db, album_id=album_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="Album not found")
        
    # Handle both legacy Dict return (from old crud) and new ORM Object return
    if isinstance(result, dict) and "album" in result:
        album = result["album"]
        images_in_album = result["images"]
    else:
        # Assuming lazy="selectin" is enabled in models.py, we can access images directly
        album = result
        images_in_album = album.images

    # Check for safe_mode
    safe_mode_enabled = request.cookies.get("safe_mode", "off") == "on"
    
    if safe_mode_enabled:
        images_in_album = [img for img in images_in_album if not img.is_nsfw]

    return templates.TemplateResponse("albums/album_detail.html", {
        "request": request,
        "album": album,
        "images": images_in_album,
        "image_count": len(images_in_album),
        "page_title": f"Album: {album.name}",
        "now": datetime.datetime.now,
        "safe_mode": safe_mode_enabled
    })

@router.get("/albums/new", response_class=HTMLResponse, name="create_album_form")
async def show_create_album_form(request: Request):
    """Serves the form for creating a new album."""
    return templates.TemplateResponse("albums/create_album.html", {
        "request": request,
        "page_title": "Create New Album",
        "now": datetime.datetime.now,
    })

@router.post("/albums/new", response_class=RedirectResponse)
async def handle_create_album_form(
    request: Request, 
    db: AsyncSession = Depends(get_db)
):
    """Processes the submission of the create album form."""
    form_data = await request.form()
    
    # Use the schema from features.albums.schemas
    album_create_schema = album_schemas.AlbumCreate(
        name=form_data.get("name"),
        description=form_data.get("description")
    )
    
    new_album = await album_service.create_album(db, album=album_create_schema)
    
    # Handle potential dict return from legacy service code
    if isinstance(new_album, dict):
        new_id = new_album['album'].id
    else:
        new_id = new_album.id

    # Redirect to the new album's page
    return RedirectResponse(
        url=request.url_for('view_album', album_id=new_id), 
        status_code=303
    )