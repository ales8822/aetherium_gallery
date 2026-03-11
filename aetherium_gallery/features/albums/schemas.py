# schemas.py - Pydantic models for Album-related data structures
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from aetherium_gallery.features.images.schemas import Image

class AlbumBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None

class AlbumCreate(AlbumBase):
    pass

class AlbumUpdate(AlbumBase):
    pass

class AlbumInfo(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True

class Album(AlbumBase):
    id: int
    created_date: datetime
    images: List[Image] = [] 

    class Config:
        from_attributes = True

class AlbumReorderRequest(BaseModel):
    image_ids: List[int]

# 1. Runtime import for the Image model
from aetherium_gallery.features.images.schemas import Image
from aetherium_gallery.features.tags.schemas import Tag

# 2. Rebuild the Album model
Album.model_rebuild()