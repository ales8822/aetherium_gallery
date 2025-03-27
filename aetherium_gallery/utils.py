import os
import uuid
from pathlib import Path
from PIL import Image as PILImage
from PIL.ExifTags import TAGS
from .config import settings
from typing import Optional, Dict, Tuple # Import Optional (and Dict/Tuple which might be needed later)
import logging
import re

logger = logging.getLogger(__name__)

THUMBNAIL_SIZE = (256, 256) # Width, Height

def generate_safe_filename(original_filename: str) -> (str, str):
    """Generates a unique, safe filename and returns the stem and extension."""
    extension = Path(original_filename).suffix.lower()
    # Sanitize extension if needed, e.g., ensure it starts with '.'
    if not extension or len(extension) > 5: # Basic sanity check
        extension = ".png" # Default or raise error
    unique_id = uuid.uuid4()
    filename_stem = str(unique_id)
    safe_filename = f"{filename_stem}{extension}"
    return filename_stem, extension, safe_filename

def save_uploaded_image(file, filename: str) -> Path:
    """Saves the uploaded file content to the designated path."""
    file_path = settings.UPLOAD_PATH / filename
    try:
        with open(file_path, "wb") as buffer:
            buffer.write(file.file.read())
        logger.info(f"Saved uploaded file to: {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"Error saving file {filename}: {e}", exc_info=True)
        # Clean up partial file if error occurs?
        if file_path.exists():
            try:
                os.remove(file_path)
            except OSError:
                logger.error(f"Could not remove partially saved file {file_path}")
        raise # Re-raise the exception to be handled by the route

def generate_thumbnail(image_path: Path, filename_stem: str, extension: str) -> Optional[str]:
    """Generates a thumbnail for the given image."""
    thumbnail_filename = f"{filename_stem}_thumb{extension}"
    thumbnail_filepath = settings.UPLOAD_PATH / thumbnail_filename
    try:
        with PILImage.open(image_path) as img:
            # Ensure image mode is suitable for saving in common formats (like PNG/JPEG)
            if img.mode not in ('RGB', 'RGBA', 'L'):
                 img = img.convert('RGB')

            img.thumbnail(THUMBNAIL_SIZE)
            img.save(thumbnail_filepath)
            logger.info(f"Generated thumbnail: {thumbnail_filepath}")
            return thumbnail_filename # Return relative path/filename
    except Exception as e:
        logger.error(f"Error generating thumbnail for {image_path}: {e}", exc_info=True)
        return None

def parse_metadata_from_image(image_path: Path) -> dict:
    """
    Placeholder: Attempts to parse metadata (EXIF, potentially text chunks for SD)
    Returns a dictionary of found metadata fields.
    """
    metadata = {}
    try:
        with PILImage.open(image_path) as img:
            metadata['width'] = img.width
            metadata['height'] = img.height

            # --- Attempt to read EXIF data ---
            exif_data = img.getexif()
            if exif_data:
                for tag_id, value in exif_data.items():
                    tag_name = TAGS.get(tag_id, tag_id)
                    # Handle specific tags if needed, e.g., UserComment often has parameters
                    if tag_name == 'UserComment':
                        try:
                            # Decode based on potential encodings
                            comment = value.decode('utf-8', errors='ignore')
                            # Try parsing Stable Diffusion parameters (example)
                            sd_params = parse_sd_parameters(comment)
                            metadata.update(sd_params)
                        except Exception:
                            pass # Ignore decoding/parsing errors for now
                    # Add other relevant EXIF tags if desired
                    # metadata[str(tag_name)] = value # Be careful, values can be complex

            # --- Attempt to read Stable Diffusion parameters from PNG info chunks ---
            if 'parameters' in img.info:
                sd_params = parse_sd_parameters(img.info['parameters'])
                metadata.update(sd_params)

    except Exception as e:
        logger.warning(f"Could not read metadata from {image_path}: {e}")

    return metadata

def parse_sd_parameters(param_string: str) -> dict:
    """Parses a typical Stable Diffusion parameter string."""
    params = {}
    # Handle multi-line prompts first
    prompt_match = re.match(r"(.*?)(Negative prompt:|$)", param_string, re.DOTALL | re.IGNORECASE)
    if prompt_match:
        params['prompt'] = prompt_match.group(1).strip()
        remaining_string = param_string[len(prompt_match.group(0)):]
    else:
        params['prompt'] = None # Or set to the whole string if no negative prompt found?
        remaining_string = "" # Assume the rest might be key-value pairs

    # Find Negative Prompt
    neg_prompt_match = re.search(r"Negative prompt:\s*(.*?)(Steps:|$)", param_string, re.DOTALL | re.IGNORECASE)
    if neg_prompt_match:
        params['negative_prompt'] = neg_prompt_match.group(1).strip()
        # Update remaining string if needed, though key-value parsing might handle overlaps
        # Note: This simple regex might fail with complex prompts containing the keywords.
        # A more robust parser might be needed for edge cases.

    # Find key-value pairs (like Steps, Sampler, CFG scale, Seed, etc.)
    # Regex to find "Key: Value" pairs, handling potential commas and spaces
    kv_matches = re.findall(r"([a-zA-Z\s]+):\s*([^,]+(?:,\s*[^:]+)*?)(?:,|$)", param_string)

    for key, value in kv_matches:
        key = key.strip().lower().replace(" ", "_") # Normalize key
        value = value.strip()

        # Try to convert values to appropriate types
        try:
            if key == 'seed':
                params[key] = int(value)
            elif key in ['cfg_scale', 'cfg']: # Handle alias 'cfg'
                params['cfg_scale'] = float(value)
            elif key == 'steps':
                params[key] = int(value)
            elif key == 'sampler':
                 params[key] = value
            elif key == 'model_hash':
                 params[key] = value
            # Add more specific keys as needed (Size, Model, etc.)
            # elif key == 'size':
            #    match = re.match(r'(\d+)x(\d+)', value)
            #    if match:
            #        params['width'] = int(match.group(1))
            #        params['height'] = int(match.group(2))
        except ValueError:
            # If conversion fails, store as string or log warning
            logger.warning(f"Could not convert metadata key '{key}' value '{value}'")
            if key not in params: # Don't overwrite if already parsed (e.g., prompt)
                params[key] = value

    # Clean up prompt/negative prompt from key-value parsing if they were caught
    params.pop('negative_prompt', None) # Remove if parsed as a key
    if 'prompt' in params and params['prompt'] == '': # If kv parsing blanked the prompt
        params.pop('prompt')

    # Final cleanup if needed
    if 'prompt' in params and params['prompt'] is not None:
       # Remove trailing parameter string if accidentally included in prompt
       if "Negative prompt:" in params['prompt']:
           params['prompt'] = params['prompt'].split("Negative prompt:")[0].strip()
       if "Steps:" in params['prompt']:
           params['prompt'] = params['prompt'].split("Steps:")[0].strip()


    return params

def delete_image_files(filename: str, thumbnail_filename: Optional[str]):
    """Deletes the main image file and its thumbnail."""
    main_path = settings.UPLOAD_PATH / filename
    paths_to_delete = [main_path]
    if thumbnail_filename:
        thumb_path = settings.UPLOAD_PATH / thumbnail_filename
        paths_to_delete.append(thumb_path)

    deleted_count = 0
    for path in paths_to_delete:
        try:
            if path.exists():
                os.remove(path)
                logger.info(f"Deleted file: {path}")
                deleted_count += 1
        except OSError as e:
            logger.error(f"Error deleting file {path}: {e}")
    return deleted_count > 0 # Return True if at least one file was deleted