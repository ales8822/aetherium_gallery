# schemas.py - Pydantic models for tag-related data structures
from pydantic import BaseModel
from typing import List

class TagBase(BaseModel):
    name: str

class TagCreate(TagBase):
    pass

class Tag(TagBase):
    id: int
    
    class Config:
        from_attributes = True

# For forward references in other schemas
class TagInfo(Tag):
    pass
