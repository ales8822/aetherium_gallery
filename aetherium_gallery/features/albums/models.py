from sqlalchemy import Column, Integer, String, DateTime, Text, func
from sqlalchemy.orm import relationship
from aetherium_gallery.core.database import Base

class Album(Base):
    __tablename__ = "albums"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    created_date = Column(DateTime(timezone=True), server_default=func.now())

    # relationship to Image using string reference
    images = relationship(
        "Image",
        back_populates="album",
        cascade="all, delete-orphan",
        # Note: order_by will be handled in the service layer or by string ref if possible,
        # but for now we follow the instruction to use string relationships.
        # Original code used lambda: models.Image.order_index, which is tricky with split files.
        # We'll use "Image.order_index" as a string.
        order_by="Image.order_index",
        lazy="selectin" 
    )

    def __repr__(self):
        return f"<Album(id={self.id}, name='{self.name}')>"
