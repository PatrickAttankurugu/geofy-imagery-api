import subprocess
import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import cloudinary
import cloudinary.uploader
from PIL import Image
import rasterio
import google.generativeai as genai
from .config import settings

# Configure services
cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET
)
genai.configure(api_key=settings.GEMINI_API_KEY)

class ImageryService:
    """All imagery processing logic"""
    
    def __init__(self):
        self.temp_dir = Path(settings.TEMP_STORAGE_PATH)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
    def check_availability(self, lat: float, lon: float) -> List[str]:
        """Check available dates using GEHistoricalImagery"""
        try:
            result = subprocess.run(
                [
                    settings.GEHISTORICALIMAGERY_PATH,
                    'availability',
                    '--lat', str(lat),
                    '--lon', str(lon),
                    '--provider', 'google'
                ],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                raise Exception(f"Availability check failed: {result.stderr}")
            
            # Parse output to get available dates
            dates = self._parse_availability_output(result.stdout)
            return dates
            
        except subprocess.TimeoutExpired:
            raise Exception("Availability check timed out")
        except Exception as e:
            raise Exception(f"Failed to check availability: {str(e)}")
    
    def download_imagery(
        self, 
        lat: float, 
        lon: float, 
        date: str, 
        zoom: int,
        job_id: str
    ) -> str:
        """Download imagery for a specific date"""
        output_path = self.temp_dir / f"{job_id}_{date}.tif"
        
        try:
            result = subprocess.run(
                [
                    settings.GEHISTORICALIMAGERY_PATH,
                    'download',
                    '--lat', str(lat),
                    '--lon', str(lon),
                    '--date', date,
                    '--zoom', str(zoom),
                    '--output', str(output_path),
                    '--provider', 'google'
                ],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode != 0:
                raise Exception(f"Download failed: {result.stderr}")
            
            if not output_path.exists():
                raise Exception("Output file not created")
            
            return str(output_path)
            
        except subprocess.TimeoutExpired:
            raise Exception("Download timed out")
        except Exception as e:
            raise Exception(f"Failed to download imagery: {str(e)}")
    
    def convert_geotiff_to_png(self, tif_path: str) -> str:
        """Convert GeoTIFF to PNG"""
        png_path = tif_path.replace('.tif', '.png')
        
        try:
            # Read GeoTIFF
            with rasterio.open(tif_path) as src:
                # Read RGB bands (assuming bands 1,2,3 are RGB)
                data = src.read([1, 2, 3])
                
                # Convert to PIL Image
                # Transpose from (bands, height, width) to (height, width, bands)
                data = data.transpose(1, 2, 0)
                img = Image.fromarray(data)
                
                # Save as PNG
                img.save(png_path, 'PNG')
            
            return png_path
            
        except Exception as e:
            raise Exception(f"Failed to convert GeoTIFF: {str(e)}")
    
    def upload_to_cloudinary(self, image_path: str, job_id: str, year: int) -> Dict[str, str]:
        """Upload image to Cloudinary and return URLs"""
        try:
            # Upload original
            upload_result = cloudinary.uploader.upload(
                image_path,
                folder=f"geofy/{job_id}",
                public_id=f"imagery_{year}",
                resource_type="image"
            )
            
            # Generate URLs
            urls = {
                'original': upload_result['secure_url'],
                'optimized': cloudinary.CloudinaryImage(upload_result['public_id']).build_url(
                    quality="auto",
                    fetch_format="auto"
                ),
                'thumbnail': cloudinary.CloudinaryImage(upload_result['public_id']).build_url(
                    width=400,
                    height=300,
                    crop="fill"
                )
            }
            
            return urls
            
        except Exception as e:
            raise Exception(f"Failed to upload to Cloudinary: {str(e)}")
    
    def analyze_with_gemini(self, image_paths: List[str]) -> Dict[str, Any]:
        """Analyze images with Gemini AI"""
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            # Prepare images
            images = []
            for path in image_paths:
                img = Image.open(path)
                images.append(img)
            
            # Create prompt
            prompt = """
            Analyze these historical satellite images in chronological order.
            Identify:
            1. Major structural changes (buildings, roads, land use)
            2. Timeline of development
            3. Notable patterns or trends
            
            Provide analysis in JSON format with keys:
            - changes_detected: List of changes
            - timeline: Year-by-year progression
            - summary: Overall assessment
            """
            
            # Generate analysis
            response = model.generate_content([prompt] + images)
            
            # Parse response
            analysis = json.loads(response.text) if response.text else {}
            
            return analysis
            
        except Exception as e:
            return {
                "error": f"AI analysis failed: {str(e)}",
                "changes_detected": [],
                "timeline": [],
                "summary": "Analysis unavailable"
            }
    
    def cleanup_temp_files(self, job_id: str):
        """Clean up temporary files for a job"""
        try:
            for file in self.temp_dir.glob(f"{job_id}_*"):
                file.unlink()
        except Exception as e:
            print(f"Cleanup warning: {e}")
    
    def _parse_availability_output(self, output: str) -> List[str]:
        """Parse GEHistoricalImagery availability output"""
        # TODO: Implement actual parsing based on tool output format
        # For now, return mock dates in range 2018-2025
        return ['2018-01-01', '2019-01-01', '2020-01-01', 
                '2021-01-01', '2022-01-01', '2023-01-01',
                '2024-01-01', '2025-01-01']

class WebhookService:
    """Handle webhook callbacks"""
    
    @staticmethod
    async def send_webhook(url: str, payload: Dict[str, Any]):
        """Send webhook with retry logic"""
        import httpx
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(url, json=payload)
                    if response.status_code < 300:
                        return True
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                # Exponential backoff
                await asyncio.sleep(2 ** attempt)
        
        return False