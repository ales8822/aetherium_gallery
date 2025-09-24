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
import json 
import ffmpeg 

logger = logging.getLogger(__name__)

THUMBNAIL_SIZE = (400, 400) # Width, Height

def generate_safe_filename(original_filename: str) -> Tuple[str, str, str]: # Corrected type hint
    """Generates a unique, safe filename and returns the stem, extension, and full name."""
    extension = Path(original_filename).suffix.lower()
    if not extension or len(extension) > 5:
        extension = ".png"
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
def generate_thumbnail(image_path: Path, filename_stem: str) -> Optional[str]:
    """Generates a thumbnail for a given image file."""
    try:
        # 1. Define the output filename with the correct extension
        thumbnail_filename = f"{filename_stem}_thumb.webp"
        
        # 2. Ensure the 'thumbnails' subdirectory exists
        thumbnail_dir = settings.UPLOAD_PATH / "thumbnails"
        thumbnail_dir.mkdir(exist_ok=True)
        
        # 3. Define the full, correct path to save the file
        thumbnail_filepath = thumbnail_dir / thumbnail_filename

        with PILImage.open(image_path) as img:
            # Convert to RGB if necessary (e.g., from GIF, P)
            if img.mode not in ('RGB', 'RGBA'):
                 img = img.convert('RGB')
            
            # Create the thumbnail in place
            img.thumbnail(THUMBNAIL_SIZE)
            
            # 4. Save the file in WEBP format with high quality
            img.save(thumbnail_filepath, "WEBP", quality=90)
            
            logger.info(f"Generated image thumbnail: {thumbnail_filepath}")

            # 5. Return the full relative path, which matches what images.py expects
            return f"thumbnails/{thumbnail_filename}"

    except Exception as e:
        logger.error(f"Error generating image thumbnail for {image_path}: {e}", exc_info=True)
        return None

def parse_metadata_from_image(image_path: Path) -> dict:
    """Parses Stable Diffusion and other metadata from an image file."""
    metadata = {}
    try:
        with PILImage.open(image_path) as img:
            metadata['width'], metadata['height'] = img.size
            param_string = img.info.get('parameters', '') or img.info.get('prompt', '')

            if param_string:
                try: # Handle ComfyUI JSON format
                    workflow = json.loads(param_string)
                    for node in workflow.values():
                        if node.get('class_type') == "CLIPTextEncode" and 'text' in node.get('inputs', {}):
                           metadata['prompt'] = node['inputs']['text']
                           break
                    metadata['notes'] = json.dumps(workflow, indent=2)
                except json.JSONDecodeError: # Handle A1111/InvokeAI text format
                    metadata['notes'] = param_string
                    neg_prompt_match = re.search(r"Negative prompt:\s*([\s\S]+?)(?:Steps:|$)", param_string)
                    if neg_prompt_match:
                        metadata['prompt'] = param_string[:neg_prompt_match.start()].strip()
                        metadata['negative_prompt'] = neg_prompt_match.group(1).strip()
                    else:
                        metadata['prompt'] = param_string.split("Steps:")[0].strip()

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
                        except (ValueError, TypeError): continue
    except Exception as e:
        logger.warning(f"Could not read metadata from {image_path}: {e}")
    return metadata

def save_uploaded_file(file, filename: str) -> Path:
    """
    Saves any uploaded file (image or video) content to the designated path.
    Handles both FastAPI UploadFile objects and in-memory BytesIO objects.
    """
    file_path = settings.UPLOAD_PATH / filename
    try:
        if hasattr(file, 'file'):
            # It's an UploadFile, reset cursor and read
            file.file.seek(0)
            content = file.file.read()
        else:
            # It's a file-like object (BytesIO), reset cursor and read
            file.seek(0)
            content = file.read()

        with open(file_path, "wb") as buffer:
            buffer.write(content)
        
        logger.info(f"Saved uploaded file to: {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"Error saving file {filename}: {e}", exc_info=True)
        # Clean up partial file on error
        if file_path.exists():
            try:
                os.remove(file_path)
            except OSError:
                pass
        raise

def process_video_file(video_path: Path, filename_stem: str) -> tuple[dict, str]:
    # ... (This function is fine, but replacing ensures consistency)
    logger.info(f"Processing video file: {video_path}")
    output_path = video_path.with_suffix('.transcoded.mp4')
    try:
        probe = ffmpeg.probe(str(video_path))
        video_stream = next((s for s in probe['streams'] if s['codec_type'] == 'video'), None)
        if video_stream is None: raise RuntimeError("No video stream found.")
        codec_name = video_stream.get('codec_name')
        if codec_name != 'h264':
            logger.info(f"Transcoding video from {codec_name} to h264...")
            (ffmpeg.input(str(video_path)).output(str(output_path), vcodec='libx264', acodec='aac', pix_fmt='yuv420p', preset='fast').overwrite_output().run(capture_stdout=True, capture_stderr=True))
            os.replace(output_path, video_path)
            probe = ffmpeg.probe(str(video_path))
            video_stream = next((s for s in probe['streams'] if s['codec_type'] == 'video'), None)
        thumbnail_filename = f"{filename_stem}_thumb.jpg"
        thumbnail_filepath = settings.UPLOAD_PATH / thumbnail_filename
        (ffmpeg.input(str(video_path), ss=0).output(str(thumbnail_filepath), vframes=1).overwrite_output().run(capture_stdout=True, capture_stderr=True))
        metadata = {"width": int(video_stream.get('width',0)), "height": int(video_stream.get('height',0)), "duration": float(video_stream.get('duration',0.0))}
        return metadata, thumbnail_filename
    except ffmpeg.Error as e:
        if output_path.exists(): os.remove(output_path)
        raise
    except Exception as e:
        if output_path.exists(): os.remove(output_path)
        raise

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