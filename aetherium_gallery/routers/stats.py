# aetherium_gallery/routers/stats.py

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
import datetime

from .. import crud
from ..database import get_db
from ..config import BASE_DIR

router = APIRouter(
    prefix="/stats",
    tags=["Statistics Frontend"],
)

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

@router.get("/", response_class=HTMLResponse, name="view_stats")
async def show_statistics_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Serves the main statistics dashboard page."""
    
    stats_data = await crud.get_gallery_statistics(db)

    # Simple helper to format bytes into KB, MB, GB, etc.
    def format_bytes(size):
        if size == 0:
            return "0B"
        power = 1024
        n = 0
        power_labels = {0: '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
        while size > power and n < len(power_labels) -1 :
            size /= power
            n += 1
        return f"{size:.2f} {power_labels[n]}B"

    # Add the formatted size to our stats dict
    stats_data["total_size_formatted"] = format_bytes(stats_data["total_size_bytes"])

    return templates.TemplateResponse("stats.html", {
        "request": request,
        "stats": stats_data,
        "page_title": "Gallery Statistics",
        "now": datetime.datetime.now,
    })