from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from . import models, schemas
from typing import List, Optional

# --- Image CRUD ---

async def get_image(db: AsyncSession, image_id: int) -> Optional[models.Image]:
    """Get a single image by its ID."""
    result = await db.execute(select(models.Image).filter(models.Image.id == image_id))
    return result.scalars().first()

async def get_images(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[models.Image]:
    """Get a list of images with pagination."""
    result = await db.execute(
        select(models.Image)
        .order_by(models.Image.upload_date.desc()) # Example sorting
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

async def create_image(db: AsyncSession, image_data: dict) -> models.Image:
    """Create a new image record in the database."""
    # Potentially use schemas.ImageCreate here for validation if needed
    db_image = models.Image(**image_data)
    db.add(db_image)
    await db.commit()
    await db.refresh(db_image)
    return db_image

async def update_image(db: AsyncSession, db_image: models.Image, image_update: schemas.ImageUpdate) -> models.Image:
    """Update an existing image record."""
    update_data = image_update.model_dump(exclude_unset=True) # Pydantic V2
    for key, value in update_data.items():
        setattr(db_image, key, value)
    db.add(db_image)
    await db.commit()
    await db.refresh(db_image)
    return db_image

async def delete_image(db: AsyncSession, image_id: int) -> Optional[models.Image]:
    """Delete an image record from the database."""
    db_image = await get_image(db, image_id)
    if db_image:
        await db.delete(db_image)
        await db.commit()
        return db_image
    return None


# --- Add CRUD functions for Tags and Albums later ---
# async def create_tag(...): ...
# async def get_tags(...): ...
# async def create_album(...): ...
# async def get_albums(...): ...
# async def add_image_to_album(...): ...
# async def assign_tag_to_image(...): ...