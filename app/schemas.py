from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

# Request Schemas
class CaptureRequest(BaseModel):
    coordinates: str = Field(..., description="Latitude,Longitude")
    locationName: str = Field(..., description="Human-readable location name")
    zoomLevel: int = Field(250, ge=100, le=1000)
    callbackUrl: Optional[str] = None
    
    @validator('coordinates')
    def validate_coordinates(cls, v):
        try:
            parts = v.split(',')
            if len(parts) != 2:
                raise ValueError("Must be 'latitude,longitude'")
            lat, lon = float(parts[0]), float(parts[1])
            if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                raise ValueError("Invalid coordinate range")
            return v
        except Exception as e:
            raise ValueError(f"Invalid coordinates: {e}")

# Response Schemas
class CaptureResponse(BaseModel):
    success: bool
    jobId: str
    status: str
    message: str
    estimatedTime: Optional[str] = "5-15 minutes"

class ImageryItem(BaseModel):
    year: int
    captureDate: str
    imageUrl: str
    optimizedUrl: str
    thumbnailUrl: str

class JobStatusResponse(BaseModel):
    success: bool
    jobId: str
    status: JobStatus
    progress: int
    startTime: datetime
    completedAt: Optional[datetime] = None
    error: Optional[str] = None

class ImageryResponse(BaseModel):
    success: bool
    jobId: str
    location: str
    coordinates: str
    images: List[ImageryItem]
    aiAnalysis: Optional[Dict[str, Any]] = None
    processingTime: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    version: str = "1.0.0"