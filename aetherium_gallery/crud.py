from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
# Add this new import for optimized loading
from sqlalchemy.orm import selectinload 
from . import models, schemas
from typing import List, Optional
from sqlalchemy import or_

# --- Image CRUD ---

async def get_image(db: AsyncSession, image_id: int) -> Optional[models.Image]:
    """Get a single image by its ID, eagerly loading its tags."""
    result = await db.execute(
        select(models.Image)
        .options(selectinload(models.Image.tags)) # Eagerly load tags
        .filter(models.Image.id == image_id)
    )
    return result.scalars().first()

async def get_images(
    db: AsyncSession, skip: int = 0, limit: int = 100, safe_mode: bool = False
) -> List[models.Image]:
    """Get a list of images, eagerly loading their tags."""
    query = select(models.Image).options(selectinload(models.Image.tags))
    if safe_mode:
        query = query.filter(models.Image.is_nsfw == False)
    query = query.order_by(models.Image.upload_date.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

async def create_image(db: AsyncSession, image_data: dict) -> models.Image:
    """Create a new image, processing and linking any associated tags."""
    # Pop tags from the dict if they exist, so we can handle them separately
    tag_names_str = image_data.pop('tags', None)
    
    # Create the Image object without the tags first
    db_image = models.Image(**image_data)

    # If there are tags, process them
    if tag_names_str:
        tag_names = [name.strip().lower() for name in tag_names_str.split(',') if name.strip()]
        tags = await get_or_create_tags_by_name(db, tag_names)
        db_image.tags = tags # Associate the tags with the image

    db.add(db_image)
    await db.commit()
    await db.refresh(db_image)
    return db_image

async def update_image(db: AsyncSession, db_image: models.Image, image_update: schemas.ImageUpdate) -> models.Image:
    """Update an existing image record, including its tags."""
    update_data = image_update.model_dump(exclude_unset=True)
    
    # Handle tags separately
    if 'tags' in update_data:
        tag_names_str = update_data.pop('tags')
        tag_names = [name.strip().lower() for name in tag_names_str.split(',') if name.strip()]
        tags = await get_or_create_tags_by_name(db, tag_names)
        db_image.tags = tags

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


async def get_or_create_tags_by_name(db: AsyncSession, tag_names: List[str]) -> List[models.Tag]:
    """
    For a list of tag names, retrieves existing tags and creates any that don't exist.
    """
    # Find all existing tags in one query
    existing_tags_query = await db.execute(select(models.Tag).where(models.Tag.name.in_(tag_names)))
    existing_tags = existing_tags_query.scalars().all()
    existing_tag_names = {tag.name for tag in existing_tags}

    # Determine which tags are new
    new_tag_names = [name for name in tag_names if name not in existing_tag_names]

    new_tags = []
    if new_tag_names:
        # Create all new tags
        new_tags = [models.Tag(name=name) for name in new_tag_names]
        db.add_all(new_tags)
        # We need to flush to get the IDs of the new tags if we were to return them
        # before the final commit, but we can let the main function commit.

    return existing_tags + new_tags

async def get_images_by_tag(
    db: AsyncSession, tag_name: str, safe_mode: bool = False, skip: int = 0, limit: int = 100
) -> List[models.Image]:
    """
    Get all images associated with a specific tag name.
    """
    query = (
        select(models.Image)
        .options(selectinload(models.Image.tags))
        .join(models.Image.tags)
        .filter(models.Tag.name == tag_name)
    )
    if safe_mode:
        query = query.filter(models.Image.is_nsfw == False)
    
    query = query.order_by(models.Image.upload_date.desc()).offset(skip).limit(limit)
    
    result = await db.execute(query)
    return result.scalars().all()


async def bulk_update_images(db: AsyncSession, action_request: schemas.BulkActionRequest, utils_module) -> int:
    """
    Performs a bulk action on a list of image IDs.
    Returns the number of affected images.
    """
    if not action_request.image_ids:
        return 0

    # Fetch all the images to be updated in a single query
    images_query = await db.execute(
        select(models.Image)
        .options(selectinload(models.Image.tags)) # Eagerly load tags for modification
        .filter(models.Image.id.in_(action_request.image_ids))
    )
    images_to_update = images_query.scalars().all()

    # --- Perform the requested action ---

    if action_request.action == 'add_tags' and isinstance(action_request.value, str):
        tag_names_str = action_request.value
        tag_names = [name.strip().lower() for name in tag_names_str.split(',') if name.strip()]
        if not tag_names:
            return 0
        
        tags_to_add = await get_or_create_tags_by_name(db, tag_names)
        for image in images_to_update:
            # Add new tags, avoiding duplicates
            existing_image_tags = {tag.name for tag in image.tags}
            for tag in tags_to_add:
                if tag.name not in existing_image_tags:
                    image.tags.append(tag)
    
    elif action_request.action == 'set_nsfw' and isinstance(action_request.value, bool):
        is_nsfw_value = action_request.value
        for image in images_to_update:
            image.is_nsfw = is_nsfw_value

    elif action_request.action == 'delete':
        for image in images_to_update:
            # Use the existing utility function to delete the files
            utils_module.delete_image_files(image.filename, image.thumbnail_path)
            # Then delete the image from the session
            await db.delete(image)

    else:
        # If the action is unknown, do nothing
        return 0
        
    # Commit all changes to the database at once
    await db.commit()

    return len(images_to_update)
# --- Add CRUD functions for Tags and Albums later ---
# async def create_tag(...): ...
# async def get_tags(...): ...
# async def create_album(...): ...
# async def get_albums(...): ...
# async def add_image_to_album(...): ...
# async def assign_tag_to_image(...): ...