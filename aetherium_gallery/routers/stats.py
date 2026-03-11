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
        # 1. Fetch data from service
        raw_stats = await image_service.get_gallery_statistics(db)
    except Exception as e:
        print(f"Error fetching stats: {e}")
        raw_stats = {}

    # 2. Helper to format bytes
    def format_bytes(size):
        if size is None or size == 0: return "0B"
        power = 1024
        n = 0
        power_labels = {0: '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
        while size > power and n < len(power_labels) - 1:
            size /= power
            n += 1
        return f"{size:.2f} {power_labels[n]}B"

    # 3. CONSTRUCT FINAL DATA
    # We ensure every key used in stats.html is defined here
    stats_data = {
        "total_items": raw_stats.get("total_items", 0),
        "image_count": raw_stats.get("image_count", 0),
        "video_count": raw_stats.get("video_count", 0),
        "total_size_formatted": format_bytes(raw_stats.get("total_size_bytes", 0)),
        "nsfw_counts": raw_stats.get("nsfw_counts", {"sfw": 0, "nsfw": 0}),
        "top_tags": raw_stats.get("top_tags", []),
        "top_samplers": raw_stats.get("top_samplers", []),
        # Keep other counts for future use
        "tags_count": raw_stats.get("tags_count", 0),
        "albums_count": raw_stats.get("albums_count", 0),
    }

    return templates.TemplateResponse("stats.html", {
        "request": request,
        "stats": stats_data,
        "page_title": "Gallery Statistics",
        "now": datetime.datetime.now,
    })