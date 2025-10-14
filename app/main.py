from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
import asyncio
from datetime import datetime

from .database import engine, Base, get_db, SessionLocal
from .models import Job, JobStatus
from .schemas import (
    CaptureRequest, CaptureResponse, JobStatusResponse,
    ImageryResponse, HealthResponse, ImageryItem
)
from .services import ImageryService, WebhookService
from .config import settings

# Create tables
Base.metadata.create_all(bind=engine)

# Initialize FastAPI
app = FastAPI(
    title="Geofy Historical Imagery API",
    description="Historical satellite imagery capture for municipal property monitoring",
    version="1.0.0"
)

# Initialize services
imagery_service = ImageryService()
webhook_service = WebhookService()

# Background processing function
async def process_imagery_job(job_id: str, coordinates: str, zoom: int, callback_url: str = None):
    """Process imagery capture job"""
    # Create a new database session for this background task
    db = SessionLocal()
    
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        
        if not job:
            print(f"Error: Job {job_id} not found")
            return
        
        # Update status
        job.status = JobStatus.PROCESSING
        job.progress = 10
        db.commit()
        
        # Parse coordinates
        lat, lon = map(float, coordinates.split(','))
        
        # Check availability
        job.progress = 20
        db.commit()
        available_dates = imagery_service.check_availability(lat, lon)
        
        # Filter for 2018-2025
        target_years = range(2018, 2026)
        dates_to_download = [d for d in available_dates if any(str(y) in d for y in target_years)]
        
        if not dates_to_download:
            raise Exception("No imagery available for 2018-2025")
        
        # Download and process each year
        results = []
        progress_per_year = 60 / len(dates_to_download)
        
        for idx, date in enumerate(dates_to_download):
            # Download - returns path like: /temp/jobid_2018-01-01.tif
            tif_path = imagery_service.download_imagery(
                lat, lon, date, zoom, job_id
            )
            
            # Convert to PNG - returns path like: /temp/jobid_2018-01-01.png
            png_path = imagery_service.convert_geotiff_to_png(tif_path)
            
            # Upload to Cloudinary
            year = int(date.split('-')[0])
            urls = imagery_service.upload_to_cloudinary(png_path, job_id, year)
            
            results.append({
                'year': year,
                'captureDate': date,
                'imageUrl': urls['original'],
                'optimizedUrl': urls['optimized'],
                'thumbnailUrl': urls['thumbnail']
            })
            
            # Update progress
            job.progress = int(20 + ((idx + 1) * progress_per_year))
            db.commit()
        
        # AI Analysis
        job.progress = 85
        db.commit()
        
        # Build correct image paths - should match what convert_geotiff_to_png returns
        # Pattern: {job_id}_{date}.png where date is like "2018-01-01"
        image_paths = [
            str(imagery_service.temp_dir / f"{job_id}_{d}.png")
            for d in dates_to_download
        ]
        
        ai_analysis = imagery_service.analyze_with_gemini(image_paths)
        
        # Save results
        job.imagery_data = {'images': results}
        job.ai_analysis = ai_analysis
        job.status = JobStatus.COMPLETED
        job.progress = 100
        job.completed_at = datetime.utcnow()
        db.commit()
        
        # Cleanup
        imagery_service.cleanup_temp_files(job_id)
        
        # Send webhook if provided
        if callback_url:
            webhook_payload = {
                'jobId': job_id,
                'status': 'completed',
                'images': results,
                'aiAnalysis': ai_analysis,
                'deliveredAt': datetime.utcnow().isoformat() + 'Z'
            }
            try:
                await webhook_service.send_webhook(callback_url, webhook_payload, event="job.completed")
            except Exception as webhook_error:
                print(f"Webhook send failed: {webhook_error}")
        
    except Exception as e:
        print(f"Job {job_id} failed: {str(e)}")
        
        # Get job again in case session was closed
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            db.commit()
        
        # Send failure webhook
        if callback_url:
            try:
                await webhook_service.send_webhook(callback_url, {
                    'jobId': job_id,
                    'status': 'failed',
                    'error': str(e),
                    'deliveredAt': datetime.utcnow().isoformat() + 'Z'
                }, event="job.failed")
            except Exception as webhook_error:
                print(f"Failure webhook send failed: {webhook_error}")
    
    finally:
        db.close()

# Routes
@app.get("/api/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "version": "1.0.0"
    }

@app.post("/api/capture", response_model=CaptureResponse)
async def capture_imagery(
    request: CaptureRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Start imagery capture job"""
    # Create job
    job = Job(
        coordinates=request.coordinates,
        location_name=request.locationName,
        zoom_level=request.zoomLevel,
        callback_url=request.callbackUrl,
        status=JobStatus.QUEUED
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    # Start background processing
    background_tasks.add_task(
        process_imagery_job,
        job.id,
        request.coordinates,
        request.zoomLevel,
        request.callbackUrl
    )
    
    return {
        "success": True,
        "jobId": job.id,
        "status": "queued",
        "message": "Imagery capture job started",
        "estimatedTime": "5-15 minutes"
    }

@app.get("/api/status/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    """Get job status"""
    job = db.query(Job).filter(Job.id == job_id).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {
        "success": True,
        "jobId": job.id,
        "status": job.status,
        "progress": job.progress,
        "startTime": job.created_at,
        "completedAt": job.completed_at,
        "error": job.error_message
    }

@app.get("/api/imagery/{job_id}", response_model=ImageryResponse)
def get_imagery(job_id: str, db: Session = Depends(get_db)):
    """Get imagery results"""
    job = db.query(Job).filter(Job.id == job_id).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Job not completed")
    
    processing_time = None
    if job.completed_at:
        delta = job.completed_at - job.created_at
        processing_time = f"{delta.seconds // 60}m {delta.seconds % 60}s"
    
    return {
        "success": True,
        "jobId": job.id,
        "location": job.location_name,
        "coordinates": job.coordinates,
        "images": job.imagery_data.get('images', []) if job.imagery_data else [],
        "aiAnalysis": job.ai_analysis,
        "processingTime": processing_time
    }

@app.get("/api/jobs", response_model=List[JobStatusResponse])
def list_jobs(
    limit: int = 10,
    status: str = None,
    db: Session = Depends(get_db)
):
    """List all jobs"""
    query = db.query(Job).order_by(Job.created_at.desc())
    
    if status:
        try:
            status_enum = JobStatus(status)
            query = query.filter(Job.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    
    jobs = query.limit(limit).all()
    
    return [
        {
            "success": True,
            "jobId": job.id,
            "status": job.status,
            "progress": job.progress,
            "startTime": job.created_at,
            "completedAt": job.completed_at,
            "error": job.error_message
        }
        for job in jobs
    ]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG
    )