from sqlalchemy import Column, Integer, String, Table, ForeignKey
from aetherium_gallery.core.database import Base

# Association table for Many-to-Many relationship between Images and Tags
image_tags_association = Table(
    'image_tags', 
    Base.metadata,
    Column('image_id', Integer, ForeignKey('images.id'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tags.id'), primary_key=True)
)

class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)

    # Use string reference "Image" to avoid circular imports
    from sqlalchemy.orm import relationship
    images = relationship(
        "Image", 
        secondary=image_tags_association, 
        back_populates="tags",
        lazy="selectin"
    )

    def __repr__(self):
        return f"<Tag(id={self.id}, name='{self.name}')>"
