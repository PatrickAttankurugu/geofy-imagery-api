from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8006
    DEBUG: bool = True
    
    # Database
    DATABASE_URL: str = "sqlite:///./geofy_imagery.db"
    
    # GEHistoricalImagery
    GEHISTORICALIMAGERY_PATH: str
    
    # Cloudinary
    CLOUDINARY_CLOUD_NAME: str
    CLOUDINARY_API_KEY: str
    CLOUDINARY_API_SECRET: str
    
    # Gemini
    GEMINI_API_KEY: str
    
    # Storage
    TEMP_STORAGE_PATH: str = "./storage/temp"
    
    class Config:
        env_file = ".env"

settings = Settings()