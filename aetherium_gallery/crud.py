from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import or_, func # This is the ONLY import we need for SQL functions
from sqlalchemy import case

from . import models, schemas
from typing import List, Optional


# --- Image CRUD ---

async def get_image(db: AsyncSession, image_id: int) -> Optional[models.Image]:
    """Get a single image by its ID, eagerly loading its tags and album."""
    result = await db.execute(
        select(models.Image)
        # Chain another options() call to load the album
        .options(
            selectinload(models.Image.tags),
            selectinload(models.Image.album), # Eagerly load the album relationship
            selectinload(models.Image.video_source)
        )
        .filter(models.Image.id == image_id)
    )
    return result.scalars().first()

async def get_images(
    db: AsyncSession, 
    skip: int = 0, 
    limit: int = 100, 
    safe_mode: bool = False,
    # Add new parameter with default 'all'
    media_type: str = 'all' 
) -> List[models.Image]:
    """
    Get a list of images with pagination and optional filters.
    """
    query = select(models.Image).options(
        selectinload(models.Image.tags),
        selectinload(models.Image.video_source)
    )
    
    if safe_mode:
        query = query.filter(models.Image.is_nsfw == False)
        
    # ▼▼▼ ADD THIS NEW FILTER LOGIC ▼▼▼
    if media_type == 'video':
        # Filter for images that HAVE a video source linked
        query = query.filter(models.Image.video_source_id.isnot(None))
    elif media_type == 'image':
        # Filter for images that DO NOT have a video source
        query = query.filter(models.Image.video_source_id.is_(None))
    
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

async def get_related_images(db: AsyncSession, source_image: models.Image, limit: int = 10) -> List[models.Image]:
    """
    Finds images that share the most tags with the source_image.
    """
    # If the source image has no tags, we can't find related items.
    if not source_image.tags:
        return []

    source_tag_ids = {tag.id for tag in source_image.tags}

    # This is an advanced query. Let's break it down:
    # 1. We start with the image_tags_association table.
    # 2. We filter it to find rows where the tag_id is one of our source image's tags.
    # 3. We group by the image_id in that table.
    # 4. We count the number of matching tags for each image_id, creating a "match_count".
    # 5. We order the results so the images with the highest match_count come first.
    subquery = (
        select(
            models.image_tags_association.c.image_id,
            func.count(models.image_tags_association.c.tag_id).label("match_count"),
        )
        .where(models.image_tags_association.c.tag_id.in_(source_tag_ids))
        .group_by(models.image_tags_association.c.image_id)
        .order_by(func.count(models.image_tags_association.c.tag_id).desc())
        .subquery()
    )

    # Now, we join the Image table with our subquery result.
    query = (
        select(models.Image)
        .join(subquery, models.Image.id == subquery.c.image_id)
        # Crucially, we exclude the source image itself from the results!
        .filter(models.Image.id != source_image.id)
        # Eagerly load the data we need for the gallery display
        .options(
            selectinload(models.Image.tags),
            selectinload(models.Image.video_source)
        )
        # Order by the match_count from our subquery
        .order_by(subquery.c.match_count.desc())
        .limit(limit)
    )

    result = await db.execute(query)
    return result.scalars().all()


async def search_images(
    db: AsyncSession, 
    query: str, 
    safe_mode: bool = False, 
    media_type: str = 'all', 
    skip: int = 0, 
    limit: int = 100
) -> List[models.Image]:
    """
    Searches for images where the query string matches in the prompt,
    negative prompt, or original filename.
    """
    if not query:
        return []

    search_term = f"%{query}%"

    # Start building the database query correctly
    db_query = select(models.Image).filter(
        or_(
            models.Image.prompt.ilike(search_term),
            models.Image.negative_prompt.ilike(search_term),
            models.Image.original_filename.ilike(search_term),
        )
    )

    # Eagerly load relationships
    db_query = db_query.options(
        selectinload(models.Image.tags), 
        selectinload(models.Image.video_source)
    )

    if safe_mode:
        db_query = db_query.filter(models.Image.is_nsfw == False)
        
    if media_type == 'video':
        db_query = db_query.filter(models.Image.video_source_id.isnot(None))
    elif media_type == 'image':
        db_query = db_query.filter(models.Image.video_source_id.is_(None))
        
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
    db: AsyncSession, 
    tag_name: str, 
    safe_mode: bool = False, 
    media_type: str = 'all', 
    skip: int = 0, 
    limit: int = 100
) -> List[models.Image]:
    # ... (initial query setup is fine)
    if safe_mode:
        query = query.filter(models.Image.is_nsfw == False)
        
    # ▼▼▼ THIS IS THE FIX ▼▼▼
    # Use the 'query' variable consistently
    if media_type == 'video':
        query = query.filter(models.Image.video_source_id.isnot(None))
    elif media_type == 'image':
        query = query.filter(models.Image.video_source_id.is_(None))
        
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

    elif action_request.action == 'add_to_album':
        # The 'value' should be the integer ID of the album
        try:
            album_id = int(action_request.value) if action_request.value is not None else None
            for image in images_to_update:
                image.album_id = album_id # Set or unset the album_id
        except (ValueError, TypeError):
            return 0 # Do nothing if the album ID is invalid

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

# --- Album CRUD ---

async def get_album(db: AsyncSession, album_id: int) -> Optional[models.Album]:
    """Get a single album by its ID, eagerly loading its images and their relationships."""
    result = await db.execute(
        select(models.Album)
        .options(
            # Use a chained selectinload for nested relationships
            selectinload(models.Album.images).options(
                selectinload(models.Image.tags),         # Load tags from the Image
                selectinload(models.Image.video_source)  # ALSO load video_source from the Image
            )
        )
        .filter(models.Album.id == album_id)
    )
    return result.scalars().first()

async def get_all_albums(db: AsyncSession) -> List:
    """
    Get a list of all albums, including a count of images in each.
    Returns a list of tuples (Album, image_count).
    """
    # Create a subquery to count images per album
    image_count_subquery = (
        select(models.Image.album_id, func.count(models.Image.id).label("image_count"))
        .group_by(models.Image.album_id)
        .subquery()
    )

    query = (
        # Use func.coalesce, just like func.count
        select(models.Album, func.coalesce(image_count_subquery.c.image_count, 0))
        .outerjoin(
            image_count_subquery, models.Album.id == image_count_subquery.c.album_id
        )
        .order_by(models.Album.name)
    )

    result = await db.execute(query)
    return result.all()
    
async def create_album(db: AsyncSession, album: schemas.AlbumCreate) -> models.Album:
    """Create a new album."""
    db_album = models.Album(name=album.name, description=album.description)
    db.add(db_album)
    await db.commit()
    await db.refresh(db_album)
    return db_album

async def delete_album(db: AsyncSession, album_id: int) -> Optional[models.Album]:
    """Deletes an album. Images within the album will have their album_id set to null."""
    db_album = await get_album(db, album_id=album_id)
    if db_album:
        await db.delete(db_album)
        await db.commit()
        return db_album
    return None

# --- Video CRUD ---

async def create_video_source(db: AsyncSession, video_data: dict) -> models.VideoSource:
    """Create a new video source record in the database."""
    db_video_source = models.VideoSource(**video_data)
    db.add(db_video_source)
    await db.commit()
    await db.refresh(db_video_source)
    return db_video_source


# --- Statistics CRUD ---

async def get_gallery_statistics(db: AsyncSession) -> dict:
    """
    Performs a series of aggregation queries to get comprehensive
    statistics about the gallery.
    """
    
    # Query 1: General Counts (images, videos, total size)
    counts_query = select(
        func.count(models.Image.id).label("total_count"),
        func.count(models.Image.video_source_id).label("video_count"),
        func.sum(models.Image.size_bytes).label("total_size_images"),
        func.sum(models.VideoSource.size_bytes).label("total_size_videos")
    ).outerjoin(models.Image.video_source)
    
    counts_result = (await db.execute(counts_query)).first()
    total_items = counts_result.total_count or 0
    video_items = counts_result.video_count or 0
    image_items = total_items - video_items
    total_size = (counts_result.total_size_images or 0) + (counts_result.total_size_videos or 0)

    # Query 2: SFW vs NSFW Counts
    nsfw_query = select(
        func.count(models.Image.id).label("total"),
        func.sum(case((models.Image.is_nsfw == True, 1), else_=0)).label("nsfw_count")
    )
    nsfw_result = (await db.execute(nsfw_query)).first()
    nsfw_items = nsfw_result.nsfw_count or 0
    sfw_items = (nsfw_result.total or 0) - nsfw_items

    # Query 3: Top 10 most used tags
    top_tags_query = (
        select(models.Tag.name, func.count(models.image_tags_association.c.image_id).label("tag_count"))
        .join(models.image_tags_association, models.Tag.id == models.image_tags_association.c.tag_id)
        .group_by(models.Tag.name)
        .order_by(func.count(models.image_tags_association.c.image_id).desc())
        .limit(10)
    )
    top_tags_result = await db.execute(top_tags_query)
    top_tags = top_tags_result.all()

    # Query 4: Top 5 most used samplers
    top_samplers_query = (
        select(models.Image.sampler, func.count(models.Image.id).label("sampler_count"))
        .filter(models.Image.sampler.isnot(None))
        .group_by(models.Image.sampler)
        .order_by(func.count(models.Image.id).desc())
        .limit(5)
    )
    top_samplers_result = await db.execute(top_samplers_query)
    top_samplers = top_samplers_result.all()

    # --- Assemble the final statistics dictionary ---
    stats = {
        "total_items": total_items,
        "image_count": image_items,
        "video_count": video_items,
        "total_size_bytes": total_size,
        "nsfw_counts": {"sfw": sfw_items, "nsfw": nsfw_items},
        "top_tags": [{"name": name, "count": count} for name, count in top_tags],
        "top_samplers": [{"name": name, "count": count} for name, count in top_samplers],
    }
    
    return stats