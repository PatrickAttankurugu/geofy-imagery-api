from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8006
    DEBUG: bool = False
    
    # Database
    DATABASE_URL: str = "sqlite:///./geofy_imagery.db"
    
    # GEHistoricalImagery
    GEHISTORICALIMAGERY_PATH: str = "/app/gehinix.sh"
    
    # AWS S3
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_S3_BUCKET_NAME: str = "geofy-imagery"
    AWS_S3_REGION: str = "us-east-1"
    
    # Gemini
    GEMINI_API_KEY: str
    
    # Storage
    TEMP_STORAGE_PATH: str = "./storage/temp"
    
    # Webhooks
    WEBHOOK_SIGNING_SECRET: Optional[str] = None  # If set, payloads are HMAC signed
    WEBHOOK_REQUEST_TIMEOUT_SECONDS: int = 30
    WEBHOOK_MAX_RETRIES: int = 5
    WEBHOOK_BACKOFF_BASE_SECONDS: int = 2
    WEBHOOK_TOLERANCE_SECONDS: int = 300  # receiver-side recommended timestamp tolerance
    WEBHOOK_USER_AGENT: str = "Geofy-Imagery-API/1.0 (+https://geofy.example)"
    
    class Config:
        env_file = ".env"
        extra = "ignore"  # This allows extra fields in .env without errors

settings = Settings()