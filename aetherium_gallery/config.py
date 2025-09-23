# aetherium_gallery/config.py

import os
from pydantic_settings import BaseSettings
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv # ▼▼▼ 1. IMPORT load_dotenv ▼▼▼

# Define the base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent

# ▼▼▼ 2. DEFINE THE PATH TO THE .env FILE ▼▼▼
ENV_PATH = BASE_DIR / ".env"
print(f"--- [CONFIG] Explicitly loading .env file from: {ENV_PATH} ---")

# ▼▼▼ 3. EXPLICITLY LOAD THE .env FILE ▼▼▼
# This is the most important step. It loads the variables into the environment.
load_dotenv(dotenv_path=ENV_PATH)

class Settings(BaseSettings):
    # Now, Pydantic will read from the environment variables that we just loaded.
    DATABASE_URL: str
    UPLOAD_FOLDER: str = "uploads"
    SECRET_KEY: str = "default-secret-should-be-overridden"
    DEBUG: bool = False
    GOOGLE_API_KEY: Optional[str] = None
    
    @property
    def UPLOAD_PATH(self) -> Path:
        path = BASE_DIR / self.UPLOAD_FOLDER
        path.mkdir(parents=True, exist_ok=True)
        return path

# We no longer need the inner 'Config' class because we are loading the file manually.
# Pydantic will automatically pick up the now-loaded environment variables.

settings = Settings()