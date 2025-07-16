from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from . import models, schemas
from typing import List, Optional
from sqlalchemy import or_

# --- Image CRUD ---

async def get_image(db: AsyncSession, image_id: int) -> Optional[models.Image]:
    """Get a single image by its ID."""
    result = await db.execute(select(models.Image).filter(models.Image.id == image_id))
    return result.scalars().first()

async def get_images(
    db: AsyncSession, skip: int = 0, limit: int = 100, safe_mode: bool = False
) -> List[models.Image]:
    """
    Get a list of images with pagination and an optional NSFW filter.
    """
    query = select(models.Image)

    # If safe mode is on, add a filter to the query
    if safe_mode:
        query = query.filter(models.Image.is_nsfw == False)
    
    # Apply the rest of the query options
    query = query.order_by(models.Image.upload_date.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
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


async def search_images(
    db: AsyncSession, query: str, safe_mode: bool = False, skip: int = 0, limit: int = 100
) -> List[models.Image]:
    """
    Searches for images where the query string matches in the prompt,
    negative prompt, or original filename.
    """
    if not query:
        return []

    # The search term needs to be wrapped with % for a 'contains' search
    search_term = f"%{query}%"

    # Start building the database query
    db_query = select(models.Image).filter(
        # Use or_ to find matches in any of the specified fields
        or_(
            models.Image.prompt.ilike(search_term),
            models.Image.negative_prompt.ilike(search_term),
            models.Image.original_filename.ilike(search_term),
        )
    )

    # Apply the safe mode filter if it's enabled
    if safe_mode:
        db_query = db_query.filter(models.Image.is_nsfw == False)
    
    # Apply ordering and pagination
    db_query = db_query.order_by(models.Image.upload_date.desc()).offset(skip).limit(limit)

    result = await db.execute(db_query)
    return result.scalars().all()


# --- Add CRUD functions for Tags and Albums later ---
# async def create_tag(...): ...
# async def get_tags(...): ...
# async def create_album(...): ...
# async def get_albums(...): ...
# async def add_image_to_album(...): ...
# async def assign_tag_to_image(...): ...