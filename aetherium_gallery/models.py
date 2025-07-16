from sqlalchemy import Column, Integer, String, DateTime, Text, Float,Boolean, Table, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .database import Base
from datetime import datetime


# This table connects Images and Tags. It doesn't need its own Model class.
image_tags_association = Table('image_tags', Base.metadata,
    Column('image_id', Integer, ForeignKey('images.id'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tags.id'), primary_key=True)
)


class Image(Base):
    __tablename__ = "images"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, unique=True, index=True, nullable=False) # Stored filename (e.g., UUID based)
    original_filename = Column(String, nullable=True) # Original uploaded filename
    filepath = Column(String, nullable=False) # Path relative to UPLOAD_FOLDER
    thumbnail_path = Column(String, nullable=True) # Path for thumbnail
    upload_date = Column(DateTime(timezone=True), server_default=func.now())
    content_type = Column(String, nullable=True)
    size_bytes = Column(Integer, nullable=True)

    # --- Metadata Specific to Generated Images (Add more as needed) ---
    prompt = Column(Text, nullable=True)
    negative_prompt = Column(Text, nullable=True)
    seed = Column(Integer, nullable=True)
    cfg_scale = Column(Float, nullable=True)
    steps = Column(Integer, nullable=True)
    sampler = Column(String, nullable=True)
    model_hash = Column(String, nullable=True) # Hash or name of the generation model
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)

    # --- User Management ---
    user_rating = Column(Integer, nullable=True) # e.g., 1-5 stars
    notes = Column(Text, nullable=True)
    is_favorite = Column(Integer, default=0) # 0=False, 1=True
    is_nsfw = Column(Boolean, default=False, nullable=False, index=True)

    # ▼▼▼ ACTIVATE THE RELATIONSHIP TO TAGS ▼▼▼
    tags = relationship(
        "Tag",
        secondary=image_tags_association,
        back_populates="images",
        lazy="selectin"  # Eagerly load tags with a separate SELECT IN query
    )
    # Relationships (Add later for Tags, Albums)
    # tags = relationship("Tag", secondary="image_tags", back_populates="images")
    # album_id = Column(Integer, ForeignKey("albums.id"), nullable=True)
    # album = relationship("Album", back_populates="images")

    def __repr__(self):
        return f"<Image(id={self.id}, filename='{self.filename}')>"

class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)

    images = relationship(
        "Image",
        secondary=image_tags_association,
        back_populates="tags"
    )

    def __repr__(self):
        return f"<Tag(id={self.id}, name='{self.name}')>"

# Add Tag and Album models later
# class Tag(Base): ...
# class Album(Base): ...
# Association table for many-to-many tags:
# image_tags = Table('image_tags', Base.metadata, ...)