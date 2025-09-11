# aetherium_gallery/routers/albums.py

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
import datetime

from .. import crud, schemas
from ..database import get_db
from ..config import BASE_DIR

router = APIRouter(
    tags=["Albums Frontend"],
)

# Use the same templates instance from your frontend router
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

@router.get("/albums", response_class=HTMLResponse, name="list_albums")
async def list_all_albums(request: Request, db: AsyncSession = Depends(get_db)):
    """Serves the page that lists all created albums."""
    # The CRUD function now returns a list of (album, image_count) tuples
    albums_with_counts = await crud.get_all_albums(db)
    
    return templates.TemplateResponse("albums/album_list.html", {
        "request": request,
        "albums_with_counts": albums_with_counts, # Pass the new structure to the template
        "page_title": "All Albums",
        "now": datetime.datetime.now,
    })
    
@router.get("/album/{album_id}", response_class=HTMLResponse, name="view_album")
async def view_album_contents(request: Request, album_id: int, db: AsyncSession = Depends(get_db)):
    """Serves the gallery page for a single album."""
    # Our CRUD function now returns a dictionary {'album': ..., 'images': ...}
    # This prevents SQLAlchemy async lazy-loading errors.
    album_data = await crud.get_album(db, album_id=album_id)
    
    if not album_data:
        raise HTTPException(status_code=404, detail="Album not found")
        
    # Extract the data from the dictionary
    album = album_data["album"]
    images_in_album = album_data["images"]
    
    # Check for the safe_mode cookie
    safe_mode_enabled = request.cookies.get("safe_mode", "off") == "on"
    
    # The images list from CRUD is already sorted correctly by `order_index`.
    # We only need to apply the safe mode filter if it's enabled.
    if safe_mode_enabled:
        images_in_album = [img for img in images_in_album if not img.is_nsfw]

    return templates.TemplateResponse("albums/album_detail.html", {
        "request": request,
        "album": album,
        "images": images_in_album, # Pass the filtered and pre-sorted list
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
    album_create_schema = schemas.AlbumCreate(
        name=form_data.get("name"),
        description=form_data.get("description")
    )
    
    new_album = await crud.create_album(db, album=album_create_schema)
    
    # Redirect to the new album's page
    return RedirectResponse(
        url=request.url_for('view_album', album_id=new_album.id), 
        status_code=303
    )