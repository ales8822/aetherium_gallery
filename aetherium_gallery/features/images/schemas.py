# schemas.py - Pydantic models for image-related data structures
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from aetherium_gallery.features.albums.schemas import AlbumInfo
    from aetherium_gallery.features.tags.schemas import Tag

class VideoSourceBase(BaseModel):
    filename: str
    filepath: str
    content_type: Optional[str] = None
    size_bytes: Optional[int] = None
    duration: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None

class VideoSourceCreate(VideoSourceBase):
    pass

class VideoSource(VideoSourceBase):
    id: int
    
    class Config:
        from_attributes = True

class ImageBase(BaseModel):
    original_filename: Optional[str] = None
    prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    seed: Optional[int] = None
    cfg_scale: Optional[float] = None
    steps: Optional[int] = None
    sampler: Optional[str] = None
    model_hash: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    user_rating: Optional[int] = Field(None, ge=1, le=5)
    notes: Optional[str] = None
    is_favorite: Optional[bool] = False
    is_nsfw: Optional[bool] = False
    tags: Optional[str] = None 
    album_id: Optional[int] = None

class ImageCreate(ImageBase):
    pass

class ImageUpdate(ImageBase):
    pass

class Image(ImageBase):
    id: int
    filename: str
    filepath: str
    thumbnail_path: Optional[str] = None
    upload_date: datetime
    content_type: Optional[str] = None
    size_bytes: Optional[int] = None
    tags: List[Tag] = [] 
    album: Optional[AlbumInfo] = None
    video_source: Optional[VideoSource] = None
    map_x: Optional[float] = None
    map_y: Optional[float] = None
    
    class Config:
        from_attributes = True

class BulkActionRequest(BaseModel):
    image_ids: List[int]
    action: str 
    value: Optional[str | bool] = None


    # 1. Runtime imports to resolve forward references
from aetherium_gallery.features.albums.schemas import AlbumInfo
from aetherium_gallery.features.tags.schemas import Tag

# 2. Rebuild the Image model now that dependencies are imported
Image.model_rebuild()
