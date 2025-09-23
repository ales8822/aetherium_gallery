# aetherium_gallery/services/caption_service.py (FINAL GRADIO_CLIENT VERSION)
import asyncio # ▼▼▼ ADD THIS IMPORT ▼▼▼
from fastapi.concurrency import run_in_threadpool # ▼▼▼ ADD THIS IMPORT ▼▼▼
import google.generativeai as genai
from PIL import Image
from pathlib import Path
import logging
import os
import time

# Import the official client library
from gradio_client import Client, handle_file

logger = logging.getLogger(__name__)

# We no longer need the direct API URLs, just the name of the Hugging Face Space
HF_SPACE_NAME = "SmilingWolf/wd-tagger"

class CaptionService:
    def __init__(self):
        logger.info("Initializing API-Driven Caption Service...")
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if not google_api_key:
            self.gemini_model = None
            logger.warning("GOOGLE_API_KEY is not set. Gemini features disabled.")
        else:
            try:
                genai.configure(api_key=google_api_key)
                self.gemini_model = genai.GenerativeModel('gemini-1.5-flash-latest')
                logger.info("Gemini 1.5 Flash model configured successfully.")
            except Exception as e:
                self.gemini_model = None
                logger.error(f"Failed to configure Gemini: {e}")

        # Initialize the Gradio client for the tagger
        try:
            self.tagger_client = Client(HF_SPACE_NAME)
            logger.info(f"Gradio client for '{HF_SPACE_NAME}' initialized successfully.")
        except Exception as e:
            self.tagger_client = None
            logger.error(f"Failed to initialize Gradio client: {e}")

    async def _generate_description_from_gemini(self, image_path: Path) -> str | None:
        if not self.gemini_model: return None
        try:
            logger.info(f"Sending request to Gemini for {image_path.name}...")
            img = Image.open(image_path)
            prompt = "Describe this image in a detailed, single paragraph..."
            
            # The gemini library's generate_content is already awaitable!
            # We don't even need run_in_threadpool for this one.
            response = await self.gemini_model.generate_content_async([prompt, img], request_options={'timeout': 120})
            
            return response.text.strip()
        except Exception as e:
            logger.error(f"Error communicating with Gemini API: {e}", exc_info=True)
            return None

    async def _generate_tags_from_wd14(self, image_path: Path) -> str | None:
        """
        Uses the official Gradio Client to get tags, running the blocking
        call in a separate thread to avoid freezing the server.
        """
        if not self.tagger_client:
            logger.error("WD14 Tagger client not available.")
            return None
            
        logger.info(f"Sending request to WD14 Tagger for {image_path.name}...")
        try:
            # This is the blocking function we want to run in a thread
            def do_predict():
                result = self.tagger_client.predict(
                    image=handle_file(str(image_path)),
                    model_repo="SmilingWolf/wd-swinv2-tagger-v3",
                    general_thresh=0.35,
                    api_name="/predict"
                )
                if isinstance(result, (list, tuple)) and result:
                    tag_string = result[0]
                    cleaned_tags = tag_string.replace('_', ' ').split(',')
                    final_tags = sorted(list(set([t.strip() for t in cleaned_tags if t.strip()])))
                    return ", ".join(final_tags)
                return None

            # Use FastAPI's utility to run the sync function in an async context
            tag_result = await run_in_threadpool(do_predict)
            logger.info("Successfully received tags from WD14 Tagger.")
            return tag_result

        except Exception as e:
            logger.error(f"Error communicating with Gradio client for WD14 Tagger: {e}", exc_info=True)
            return None

    async def generate_caption(self, image_path: Path) -> dict | None:
        # Now that the helpers are true async functions, this works perfectly.
        description_task = asyncio.create_task(self._generate_description_from_gemini(image_path))
        tags_task = asyncio.create_task(self._generate_tags_from_wd14(image_path))
        
        # await the results from our concurrent tasks
        base_description = await description_task
        tags = await tags_task
        
        if not base_description:
            logger.error(f"Failed to generate base description for {image_path.name}. Aborting.")
            return None
        
        quality_prefix = "masterpiece, best quality, 8k, ultra-detailed, sharp focus"
        full_prompt = f"{quality_prefix}, {base_description}"
        negative_prompt = "low quality, worst quality, blurry, ugly, deformed, disfigured, bad anatomy"

        return {"prompt": full_prompt, "negative_prompt": negative_prompt, "tags": tags or ""}
