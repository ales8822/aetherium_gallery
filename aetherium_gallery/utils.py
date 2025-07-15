import os
import uuid
from pathlib import Path
from PIL import Image as PILImage
from PIL.ExifTags import TAGS
from .config import settings
from typing import Optional, Dict, Tuple # Import Optional (and Dict/Tuple which might be needed later)
import logging
import re
import io
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
    """
    Saves the uploaded file content to the designated path.
    Handles both FastAPI UploadFile objects and in-memory BytesIO objects.
    """
    file_path = settings.UPLOAD_PATH / filename
    try:
        # Check if the input 'file' is a FastAPI UploadFile object
        if hasattr(file, 'file'):
            # It's an UploadFile, so read from its .file attribute
            content = file.file.read()
        else:
            # Assume it's a file-like object (like BytesIO or a regular file handle)
            # and read directly from it.
            content = file.read()

        with open(file_path, "wb") as buffer:
            buffer.write(content)
        
        logger.info(f"Saved uploaded file to: {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"Error saving file {filename}: {e}", exc_info=True)
        if file_path.exists():
            try:
                os.remove(file_path)
            except OSError:
                logger.error(f"Could not remove partially saved file {file_path}")
        raise

# ▼▼▼ REPLACE THIS FUNCTION ▼▼▼
def generate_thumbnail(image_source, filename_stem: str, extension: str) -> Optional[str]:
    """
    Generates a thumbnail for the given image.
    'image_source' can be a Path object or a file-like object (BytesIO).
    """
    thumbnail_filename = f"{filename_stem}_thumb{extension}"
    thumbnail_filepath = settings.UPLOAD_PATH / thumbnail_filename
    try:
        # The 'with' statement works correctly on both Path objects and BytesIO
        with PILImage.open(image_source) as img:
            if img.mode not in ('RGB', 'RGBA', 'L'):
                 img = img.convert('RGB')

            img.thumbnail(THUMBNAIL_SIZE)
            img.save(thumbnail_filepath)
            logger.info(f"Generated thumbnail: {thumbnail_filepath}")
            return thumbnail_filename
    except Exception as e:
        logger.error(f"Error generating thumbnail for {filename_stem}: {e}", exc_info=True)
        return None


def parse_metadata_from_image(image_source) -> dict:
    """
    Parses metadata from an image.
    'image_source' can be a Path object or a file-like object (BytesIO).
    """
    metadata = {}
    try:
        # The 'with' statement works correctly on both Path objects and BytesIO
        with PILImage.open(image_source) as img:
            # We add all the parsing logic from your old `parse_sd_parameters` here
            # for a unified function.
            
            # --- Primary Data ---
            metadata['width'] = img.width
            metadata['height'] = img.height

            # --- Read PNG Info Chunks (most common for AI images) ---
            param_string = ""
            if 'parameters' in img.info:
                param_string = img.info['parameters']
            elif 'prompt' in img.info: # Handle ComfyUI style
                # This is a very basic parse, might need adjustment for complex workflows
                try:
                    workflow = json.loads(img.info['prompt'])
                    # A simplistic attempt to find a prompt node
                    for node in workflow.values():
                        if node.get('class_type') == "CLIPTextEncode" and 'text' in node.get('inputs', {}):
                           metadata['prompt'] = node['inputs']['text']
                           break # Take the first one found
                    # Fallback to just storing the workflow JSON
                    if 'prompt' not in metadata:
                        metadata['notes'] = json.dumps(workflow, indent=2)
                except json.JSONDecodeError:
                    metadata['notes'] = img.info['prompt'] # Store as raw text if not valid JSON
                param_string = metadata.get('notes', '') # Use notes for further parsing
            
            # Now we parse the parameter string we found
            if param_string:
                # Store the full raw metadata for reference
                metadata['notes'] = param_string

                # Use regex to find key-value pairs
                neg_prompt_match = re.search(r"Negative prompt:\s*([\s\S]+?)(?:Steps:|$)", param_string)
                if neg_prompt_match:
                    full_prompt = param_string[:neg_prompt_match.start()].strip()
                    metadata['prompt'] = full_prompt
                    metadata['negative_prompt'] = neg_prompt_match.group(1).strip()
                else:
                    full_prompt = param_string.split("Steps:")[0].strip()
                    metadata['prompt'] = full_prompt

                kv_matches = re.findall(r"(\w+(?: \w+)*):\s*([^,]+)", param_string)
                for key, value in kv_matches:
                    key_norm = key.strip().lower().replace(" ", "_")
                    val_norm = value.strip()
                    try:
                        if key_norm == 'steps': metadata['steps'] = int(val_norm)
                        elif key_norm == 'sampler': metadata['sampler'] = val_norm
                        elif key_norm == 'cfg_scale': metadata['cfg_scale'] = float(val_norm)
                        elif key_norm == 'seed': metadata['seed'] = int(val_norm)
                        elif key_norm == 'model_hash': metadata['model_hash'] = val_norm
                    except (ValueError, TypeError):
                        continue # Ignore conversion errors
    
    except Exception as e:
        logger.warning(f"Could not read metadata from image: {e}")

    return metadata



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