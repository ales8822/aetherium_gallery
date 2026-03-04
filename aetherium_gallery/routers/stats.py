# aetherium_gallery/routers/stats.py

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
import datetime

from ..core.database import get_db
from ..core.config import BASE_DIR
from ..features.images import service as image_service

router = APIRouter(
    prefix="/stats",
    tags=["Statistics Frontend"],
)

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

@router.get("/", response_class=HTMLResponse, name="view_stats")
async def show_statistics_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Serves the main statistics dashboard page."""
    
    try:
        # Try to get stats from the service
        raw_stats = await image_service.get_gallery_statistics(db)
        if not raw_stats:
            raw_stats = {}
    except AttributeError:
        raw_stats = {}

    # SAFE DEFAULTS: Ensure all keys exist so the template never crashes
    stats_data = {
        "total_images": raw_stats.get("total_images", 0),
        "total_size_bytes": raw_stats.get("total_size_bytes", 0),
        "nsfw_counts": raw_stats.get("nsfw_counts", {"sfw": 0, "nsfw": 0}),
        "tags_count": raw_stats.get("tags_count", 0),
        "albums_count": raw_stats.get("albums_count", 0),
        "favorites_count": raw_stats.get("favorites_count", 0),
    }

    # Helper to format bytes
    def format_bytes(size):
        if size is None or size == 0:
            return "0B"
        power = 1024
        n = 0
        power_labels = {0: '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
        while size > power and n < len(power_labels) - 1:
            size /= power
            n += 1
        return f"{size:.2f} {power_labels[n]}B"

    # Add the formatted size
    stats_data["total_size_formatted"] = format_bytes(stats_data["total_size_bytes"])

    return templates.TemplateResponse("stats.html", {
        "request": request,
        "stats": stats_data,
        "page_title": "Gallery Statistics",
        "now": datetime.datetime.now,
    })