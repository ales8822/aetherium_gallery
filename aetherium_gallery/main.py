# aetherium_gallery/main.py

import os
import uvicorn
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

# --- Import Order Matters ---
from .config import settings, BASE_DIR
from .database import init_db
from .services.vector_service import VectorService
from .routers import frontend, images, albums, stats
from .routers.api import albums as albums_api
from .routers.api import images_api as images_api

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info(f"DEBUG mode: {settings.DEBUG}")

# --- Lifespan Manager ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application startup...")
    
    # --- Initialize Database ---
    await init_db()
    logger.info("Database initialized.")

    # --- Clear FAISS index in dev mode ---
    CLEAR_INDEX_ON_STARTUP = getattr(settings, "DEBUG", False) or os.getenv("CLEAR_INDEX", "false").lower() == "true"
    if CLEAR_INDEX_ON_STARTUP:
        logger.warning("Clearing old vector index files (DEV MODE)...")
        index_file = Path("./faiss_index.bin")
        mapping_file = Path("./faiss_mapping.pkl")
        if index_file.exists():
            index_file.unlink()
        if mapping_file.exists():
            mapping_file.unlink()

    # --- Initialize Vector Service ---
    try:
        app.state.vector_service = VectorService()
        logger.info("Vector Service initialized successfully.")
    except Exception as e:
        app.state.vector_service = None
        logger.error("FATAL: Vector Service failed to initialize.", exc_info=True)

    yield  # Application runs here

    # --- Shutdown Logic ---
    logger.info("Application shutdown...")
    app.state.vector_service = None

# --- FastAPI App Instance ---
app = FastAPI(title="Aetherium Gallery", lifespan=lifespan)

# --- Mount Static and Upload Directories ---
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.mount(f"/{settings.UPLOAD_FOLDER}", StaticFiles(directory=settings.UPLOAD_PATH), name="uploads")

# --- Include Routers ---
app.include_router(frontend.router)
app.include_router(albums.router)
app.include_router(stats.router)
app.include_router(images.upload_router)
app.include_router(images.router)
app.include_router(albums_api.router)
app.include_router(images_api.router)

# --- Generic Exception Handler ---
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"message": "An internal server error occurred."})

# --- Health Check ---
@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok"}

# --- Run with Uvicorn ---
if __name__ == "__main__":
    logger.info("Running Uvicorn directly (for development only)...")
    uvicorn.run("aetherium_gallery.main:app", host="0.0.0.0", port=8000, reload=True)
