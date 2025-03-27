from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

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

    class Config:
        from_attributes = True # Pydantic V2 uses this instead of orm_mode

# --- Tag Schemas (Add Later) ---
# class TagBase(BaseModel): ...
# class TagCreate(TagBase): ...
# class Tag(TagBase): ...

# --- Album Schemas (Add Later) ---
# class AlbumBase(BaseModel): ...
# class AlbumCreate(AlbumBase): ...
# class Album(AlbumBase): ...