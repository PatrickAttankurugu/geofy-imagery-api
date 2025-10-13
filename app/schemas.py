from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from .models import JobStatus

# Request Schemas
class CaptureRequest(BaseModel):
    coordinates: str = Field(..., description="Latitude,Longitude")
    locationName: str = Field(..., description="Human-readable location name")
    zoomLevel: int = Field(18, ge=0, le=23, description="Map zoom level (0-23, default 18 for city detail)")
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