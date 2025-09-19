import os
from pydantic_settings import BaseSettings
from pathlib import Path

# Define the base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    DATABASE_URL: str
    UPLOAD_FOLDER: str = "uploads"
    SECRET_KEY: str = "default-secret-should-be-overridden"
    DEBUG: bool = False 
    # Make UPLOAD_FOLDER an absolute path
    @property
    def UPLOAD_PATH(self) -> Path:
        return BASE_DIR / self.UPLOAD_FOLDER

    class Config:
        env_file = BASE_DIR / ".env"
        env_file_encoding = 'utf-8'

settings = Settings()

# Ensure the upload directory exists
settings.UPLOAD_PATH.mkdir(parents=True, exist_ok=True)