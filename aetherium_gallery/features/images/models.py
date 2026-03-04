from sqlalchemy import Column, Integer, String, DateTime, Text, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from aetherium_gallery.core.database import Base
from aetherium_gallery.features.tags.models import image_tags_association

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

    # Coordinates for the Constellation Map
    map_x = Column(Float, nullable=True)
    map_y = Column(Float, nullable=True)
    
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
    # Used for custom sorting within an album
    order_index = Column(Integer, default=0, nullable=False)

    # --- RELATIONSHIPS ---

    # Many-to-One relationship to Album
    album_id = Column(Integer, ForeignKey("albums.id"), nullable=True, index=True)
    album = relationship("Album", back_populates="images", lazy="selectin")
    
    # Many-to-Many relationship to Tags
    tags = relationship("Tag", secondary=image_tags_association, back_populates="images", lazy="selectin")
    
    # One-to-One relationship to VideoSource
    video_source_id = Column(Integer, ForeignKey("video_sources.id"), nullable=True, index=True)
    video_source = relationship("VideoSource", back_populates="image_entry", lazy="selectin")

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
    
    # One-to-one relationship back to Image
    image_entry = relationship("Image", back_populates="video_source", uselist=False, lazy="selectin")

    def __repr__(self):
        return f"<VideoSource(id={self.id}, filename='{self.filename}')>"
