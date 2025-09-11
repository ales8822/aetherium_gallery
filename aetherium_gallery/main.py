# Add these lines at the absolute beginning of the file
import sys
import os
print("--- Debug Info ---")
print(f"Current Working Directory (CWD): {os.getcwd()}")
print("sys.path:")
for p in sys.path:
    print(f"  - {p}")
print("--- End Debug Info ---")
print("Attempting imports...") # Add this line right before the 'from fastapi import ...' line

# Existing imports follow...
from fastapi import FastAPI, Request
# ... rest of your main.py code

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import uvicorn
import logging

from .config import settings, BASE_DIR
from .database import init_db
from .routers import frontend, images, albums, stats# Import router modules

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Aetherium Gallery")

# --- Event Handlers ---
@app.on_event("startup")
async def on_startup():
    logger.info("Starting up Aetherium Gallery...")
    await init_db()
    logger.info("Database initialized.")
    logger.info(f"Upload directory: {settings.UPLOAD_PATH}")
    logger.info(f"Static files directory: {BASE_DIR / 'static'}")
    logger.info(f"Templates directory: {BASE_DIR / 'templates'}")

# --- Mount Static Files ---
# Serve the 'static' directory at the '/static' URL path
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
# Serve the 'uploads' directory at the '/uploads' URL path (adjust security in production!)
# WARNING: Directly serving the uploads folder might be a security risk.
# Consider using a dedicated file serving mechanism or cloud storage in production.
app.mount(f"/{settings.UPLOAD_FOLDER}", StaticFiles(directory=settings.UPLOAD_PATH), name="uploads")


# --- Include Routers ---
app.include_router(frontend.router)
app.include_router(images.upload_router) # User-facing upload endpoint
app.include_router(images.router) # API endpoints under /api/images
app.include_router(albums.router)
app.include_router(stats.router)

# --- Basic Error Handling (Example) ---
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"message": "An internal server error occurred."},
    )

# --- Root Path (Optional - useful for health checks or basic info) ---
@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok"}


# --- Main Execution Block (for running with `python -m aetherium_gallery.main`) ---
# Note: Typically you run FastAPI with Uvicorn directly from the terminal.
if __name__ == "__main__":
    logger.info("Running Uvicorn directly (for development only)...")
    uvicorn.run(
        "aetherium_gallery.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True, # Enable auto-reload for development
        log_level="info"
    )