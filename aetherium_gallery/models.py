# aetherium_gallery/models.py (Corrected Version)

from sqlalchemy import Column, Integer, String, DateTime, Text, Float, Boolean, Table, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base
from datetime import datetime

# --- Association Tables First ---
# It's good practice to define association tables at the top.
image_tags_association = Table('image_tags', Base.metadata,
    Column('image_id', Integer, ForeignKey('images.id'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tags.id'), primary_key=True)
)


# --- Primary Models ---

class Album(Base):
    __tablename__ = "albums"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    created_date = Column(DateTime(timezone=True), server_default=func.now())

    # This defines the "one-to-many" side: one album has many images.
    images = relationship("Image", back_populates="album", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Album(id={self.id}, name='{self.name}')>"


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)

    images = relationship("Image", secondary=image_tags_association, back_populates="tags")

    def __repr__(self):
        return f"<Tag(id={self.id}, name='{self.name}')>"


class Image(Base):
    __tablename__ = "images"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, unique=True, index=True, nullable=False)
    original_filename = Column(String, nullable=True)
    filepath = Column(String, nullable=False)
    thumbnail_path = Column(String, nullable=True)
    upload_date = Column(DateTime(timezone=True), server_default=func.now())
    content_type = Column(String, nullable=True)
    size_bytes = Column(Integer, nullable=True)

    # Metadata
    prompt = Column(Text, nullable=True)
    negative_prompt = Column(Text, nullable=True)
    seed = Column(Integer, nullable=True)
    cfg_scale = Column(Float, nullable=True)
    steps = Column(Integer, nullable=True)
    sampler = Column(String, nullable=True)
    model_hash = Column(String, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    aspect_ratio = Column(Float, nullable=True)

    # User Management
    user_rating = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)
    is_favorite = Column(Integer, default=0)
    is_nsfw = Column(Boolean, default=False, nullable=False, index=True)
    
    # --- RELATIONSHIPS ---

    # Many-to-One relationship to Album (the "many" side)
    # This is the FOREIGN KEY that links an Image to an Album.
    album_id = Column(Integer, ForeignKey("albums.id"), nullable=True, index=True)
    album = relationship("Album", back_populates="images")
    
    # Many-to-Many relationship to Tags
    tags = relationship("Tag", secondary=image_tags_association, back_populates="images", lazy="selectin")
    # This is the key: an Image post can now point to a VideoSource record.
    video_source_id = Column(Integer, ForeignKey("video_sources.id"), nullable=True, index=True)
    video_source = relationship("VideoSource", back_populates="image_entry")

    def __repr__(self):
        return f"<Image(id={self.id}, filename='{self.filename}')>"



class VideoSource(Base):
    __tablename__ = "video_sources"

    id = Column(Integer, primary_key=True, index=True)
    
    # File properties
    filename = Column(String, unique=True, nullable=False)
    filepath = Column(String, nullable=False)
    content_type = Column(String, nullable=True)
    size_bytes = Column(Integer, nullable=True)

    # Video-specific metadata
    duration = Column(Float, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    
    # This defines the "one-to-one" relationship back to the Image model.
    # A single video file is represented by a single gallery entry.
    image_entry = relationship("Image", back_populates="video_source", uselist=False)

    def __repr__(self):
        return f"<VideoSource(id={self.id}, filename='{self.filename}')>"