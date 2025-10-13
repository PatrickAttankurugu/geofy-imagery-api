from sqlalchemy import Column, String, Integer, DateTime, Enum, Text, JSON
from datetime import datetime
import uuid
import enum
from .database import Base

class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class Job(Base):
    __tablename__ = "jobs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    coordinates = Column(String, nullable=False)
    location_name = Column(String, nullable=False)
    zoom_level = Column(Integer, default=250)
    callback_url = Column(String, nullable=True)
    
    status = Column(Enum(JobStatus), default=JobStatus.QUEUED)
    progress = Column(Integer, default=0)
    
    # Results stored as JSON
    imagery_data = Column(JSON, nullable=True)
    ai_analysis = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)