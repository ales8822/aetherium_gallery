from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class TagBase(BaseModel):
    name: str

class TagCreate(TagBase):
    pass

class Tag(TagBase):
    id: int
    
    class Config:
        from_attributes = True

# --- Image Schemas ---
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
    # ▼▼▼ ADD A FIELD FOR INCOMING TAGS (as a string) ▼▼▼
    tags: Optional[str] = None # Will accept a comma-separated string from forms
    album_id: Optional[int] = None

class ImageCreate(ImageBase):
    # Fields required on creation might differ, but often overlap base
    # We will populate filename, filepath etc., during the upload process
    pass

class ImageUpdate(ImageBase):
    # Allow updating specific fields
    pass


class Image(ImageBase):
    id: int
    filename: str
    filepath: str
    thumbnail_path: Optional[str] = None
    upload_date: datetime
    content_type: Optional[str] = None
    size_bytes: Optional[int] = None
    # When displaying an image, we want a list of structured Tag objects
    tags: List[Tag] = [] # Defaults to an empty list
    # ▼▼▼ ADD A FORWARD REFERENCE TO THE ALBUM SCHEMA ▼▼▼
    # This will be populated later
    album: Optional['AlbumInfo'] = None
    class Config:
        from_attributes = True # Pydantic V2 uses this instead of orm_mode

class BulkActionRequest(BaseModel):
    image_ids: List[int]
    action: str  # e.g., 'add_tags', 'set_nsfw', 'delete'
    # 'value' can be a string (for tags) or a boolean (for nsfw)
    value: Optional[str | bool] = None

class AlbumBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None

class AlbumCreate(AlbumBase):
    pass

class AlbumUpdate(AlbumBase):
    pass

# A simplified schema for nesting inside the Image schema
class AlbumInfo(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True

# The full Album schema for detail pages
class Album(AlbumBase):
    id: int
    created_date: datetime
    images: List[Image] = [] # Show all images when viewing a single album

    class Config:
        from_attributes = True
    