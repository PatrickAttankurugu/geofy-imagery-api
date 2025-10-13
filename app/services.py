import subprocess
import os
import json
import asyncio
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
        # CRITICAL FIX: Use absolute path so CLI tool can find the directory
        self.temp_dir = Path(settings.TEMP_STORAGE_PATH).resolve()
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        print(f"[ImageryService] Initialized with temp_dir: {self.temp_dir}")
        
    def check_availability(self, lat: float, lon: float, zoom: int = 18) -> List[str]:
        """Check available dates using GEHistoricalImagery"""
        print(f"\n{'='*60}")
        print(f"[check_availability] Starting availability check")
        print(f"[check_availability] Coordinates: lat={lat}, lon={lon}, zoom={zoom}")
        
        try:
            # Create a small bounding box around the point (0.001 degree ~= 100m)
            offset = 0.001
            lower_left = f"{lat - offset},{lon - offset}"
            upper_right = f"{lat + offset},{lon + offset}"
            
            print(f"[check_availability] Bounding box:")
            print(f"  Lower-left: {lower_left}")
            print(f"  Upper-right: {upper_right}")
            
            cmd = [
                settings.GEHISTORICALIMAGERY_PATH,
                'availability',
                '--lower-left', lower_left,
                '--upper-right', upper_right,
                '--zoom', str(zoom),
                '--provider', 'TM'
            ]
            
            print(f"[check_availability] Executing command:")
            print(f"  {' '.join(cmd)}")
            
            # FIX: Capture as bytes to handle UTF-16 encoding
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=60
            )
            
            print(f"[check_availability] Command completed")
            print(f"  Return code: {result.returncode}")
            
            if result.returncode != 0:
                # Decode stderr for error messages
                try:
                    stderr_text = result.stderr.decode('utf-16-le', errors='ignore').replace('\x00', '')
                except:
                    stderr_text = result.stderr.decode('utf-8', errors='ignore')
                
                error_msg = f"Command failed with return code {result.returncode}"
                if stderr_text:
                    error_msg += f"\nError: {stderr_text}"
                print(f"[check_availability] ERROR: {error_msg}")
                raise Exception(error_msg)
            
            # FIX: Decode UTF-16LE output and strip null bytes
            try:
                stdout_text = result.stdout.decode('utf-16-le', errors='ignore')
                stdout_text = stdout_text.replace('\x00', '')
                print(f"[check_availability] Decoded as UTF-16LE")
            except:
                stdout_text = result.stdout.decode('utf-8', errors='ignore')
                print(f"[check_availability] Decoded as UTF-8")
            
            print(f"[check_availability] STDOUT length: {len(stdout_text)} chars")
            print(f"[check_availability] STDOUT:")
            print(f"{stdout_text[:500]}...")
            
            # Parse output to get available dates
            print(f"[check_availability] Parsing output for dates...")
            dates = self._parse_availability_output(stdout_text)
            print(f"[check_availability] Found {len(dates)} dates: {dates}")
            print(f"{'='*60}\n")
            
            return dates
            
        except subprocess.TimeoutExpired:
            error_msg = "Availability check timed out after 60 seconds"
            print(f"[check_availability] ERROR: {error_msg}")
            raise Exception(error_msg)
        except Exception as e:
            print(f"[check_availability] EXCEPTION: {type(e).__name__}: {str(e)}")
            print(f"{'='*60}\n")
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
        print(f"\n{'='*60}")
        print(f"[download_imagery] Starting download")
        print(f"  Job ID: {job_id}")
        print(f"  Date: {date}")
        print(f"  Coordinates: lat={lat}, lon={lon}")
        print(f"  Zoom: {zoom}")
        
        # Use absolute path for output
        output_path = self.temp_dir / f"{job_id}_{date}.tif"
        print(f"  Output path (absolute): {output_path}")
        
        try:
            # Create a small bounding box around the point
            offset = 0.001
            lower_left = f"{lat - offset},{lon - offset}"
            upper_right = f"{lat + offset},{lon + offset}"
            
            print(f"[download_imagery] Bounding box:")
            print(f"  Lower-left: {lower_left}")
            print(f"  Upper-right: {upper_right}")
            
            cmd = [
                settings.GEHISTORICALIMAGERY_PATH,
                'download',
                '--lower-left', lower_left,
                '--upper-right', upper_right,
                '--date', date,
                '--zoom', str(zoom),
                '--output', str(output_path),
                '--provider', 'TM'
            ]
            
            print(f"[download_imagery] Executing command:")
            print(f"  {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            print(f"[download_imagery] Command completed")
            print(f"  Return code: {result.returncode}")
            
            if result.stdout:
                print(f"[download_imagery] STDOUT:")
                print(f"{result.stdout}")
            
            if result.stderr:
                print(f"[download_imagery] STDERR:")
                print(f"{result.stderr}")
            
            if result.returncode != 0:
                error_msg = f"Download failed with return code {result.returncode}"
                if result.stderr:
                    error_msg += f"\nError: {result.stderr}"
                print(f"[download_imagery] ERROR: {error_msg}")
                raise Exception(error_msg)
            
            # Check if file was created
            if not output_path.exists():
                error_msg = f"Output file not created at {output_path}"
                print(f"[download_imagery] ERROR: {error_msg}")
                # List files in temp directory for debugging
                print(f"[download_imagery] Files in temp directory:")
                for f in self.temp_dir.glob("*"):
                    print(f"  {f.name} ({f.stat().st_size} bytes)")
                raise Exception(error_msg)
            
            file_size = output_path.stat().st_size
            print(f"[download_imagery] SUCCESS: File created ({file_size} bytes)")
            print(f"{'='*60}\n")
            
            return str(output_path)
            
        except subprocess.TimeoutExpired:
            error_msg = "Download timed out after 300 seconds"
            print(f"[download_imagery] ERROR: {error_msg}")
            print(f"{'='*60}\n")
            raise Exception(error_msg)
        except Exception as e:
            print(f"[download_imagery] EXCEPTION: {type(e).__name__}: {str(e)}")
            print(f"{'='*60}\n")
            raise Exception(f"Failed to download imagery: {str(e)}")
    
    def convert_geotiff_to_png(self, tif_path: str) -> str:
        """Convert GeoTIFF to PNG"""
        print(f"\n{'='*60}")
        print(f"[convert_geotiff_to_png] Starting conversion")
        print(f"  Input: {tif_path}")
        
        png_path = tif_path.replace('.tif', '.png')
        print(f"  Output: {png_path}")
        
        try:
            # Check if input file exists
            if not os.path.exists(tif_path):
                raise Exception(f"Input file does not exist: {tif_path}")
            
            file_size = os.path.getsize(tif_path)
            print(f"  Input file size: {file_size} bytes")
            
            # Read GeoTIFF
            print(f"[convert_geotiff_to_png] Opening GeoTIFF...")
            with rasterio.open(tif_path) as src:
                print(f"  Image dimensions: {src.width}x{src.height}")
                print(f"  Number of bands: {src.count}")
                print(f"  Data type: {src.dtypes[0]}")
                
                # Read RGB bands (assuming bands 1,2,3 are RGB)
                print(f"[convert_geotiff_to_png] Reading RGB bands...")
                data = src.read([1, 2, 3])
                
                # Convert to PIL Image
                # Transpose from (bands, height, width) to (height, width, bands)
                print(f"[convert_geotiff_to_png] Transposing data...")
                data = data.transpose(1, 2, 0)
                
                print(f"  Data shape: {data.shape}")
                print(f"  Data type: {data.dtype}")
                print(f"  Data range: {data.min()} to {data.max()}")
                
                # Ensure data is in uint8 format (0-255 range)
                if data.dtype != 'uint8':
                    print(f"[convert_geotiff_to_png] Normalizing to uint8...")
                    data = ((data - data.min()) / (data.max() - data.min()) * 255).astype('uint8')
                    print(f"  Normalized range: {data.min()} to {data.max()}")
                
                print(f"[convert_geotiff_to_png] Creating PIL Image...")
                img = Image.fromarray(data)
                
                # Save as PNG
                print(f"[convert_geotiff_to_png] Saving PNG...")
                img.save(png_path, 'PNG')
            
            # Verify output
            if not os.path.exists(png_path):
                raise Exception("PNG file was not created")
            
            output_size = os.path.getsize(png_path)
            print(f"[convert_geotiff_to_png] SUCCESS: PNG created ({output_size} bytes)")
            print(f"{'='*60}\n")
            
            return png_path
            
        except Exception as e:
            print(f"[convert_geotiff_to_png] EXCEPTION: {type(e).__name__}: {str(e)}")
            print(f"{'='*60}\n")
            raise Exception(f"Failed to convert GeoTIFF: {str(e)}")
    
    def upload_to_cloudinary(self, image_path: str, job_id: str, year: int) -> Dict[str, str]:
        """Upload image to Cloudinary and return URLs"""
        print(f"\n{'='*60}")
        print(f"[upload_to_cloudinary] Starting upload")
        print(f"  Image: {image_path}")
        print(f"  Job ID: {job_id}")
        print(f"  Year: {year}")
        
        try:
            # Check if file exists
            if not os.path.exists(image_path):
                raise Exception(f"Image file does not exist: {image_path}")
            
            file_size = os.path.getsize(image_path)
            print(f"  File size: {file_size} bytes")
            
            # Upload original
            print(f"[upload_to_cloudinary] Uploading to Cloudinary...")
            upload_result = cloudinary.uploader.upload(
                image_path,
                folder=f"geofy/{job_id}",
                public_id=f"imagery_{year}",
                resource_type="image"
            )
            
            print(f"[upload_to_cloudinary] Upload successful")
            print(f"  Public ID: {upload_result['public_id']}")
            print(f"  Format: {upload_result.get('format', 'unknown')}")
            print(f"  Size: {upload_result.get('bytes', 0)} bytes")
            
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
            
            print(f"[upload_to_cloudinary] URLs generated:")
            print(f"  Original: {urls['original'][:80]}...")
            print(f"  Optimized: {urls['optimized'][:80]}...")
            print(f"  Thumbnail: {urls['thumbnail'][:80]}...")
            print(f"{'='*60}\n")
            
            return urls
            
        except Exception as e:
            print(f"[upload_to_cloudinary] EXCEPTION: {type(e).__name__}: {str(e)}")
            print(f"{'='*60}\n")
            raise Exception(f"Failed to upload to Cloudinary: {str(e)}")
    
    def analyze_with_gemini(self, image_paths: List[str]) -> Dict[str, Any]:
        """Analyze images with Gemini AI"""
        print(f"\n{'='*60}")
        print(f"[analyze_with_gemini] Starting AI analysis")
        print(f"  Number of images: {len(image_paths)}")
        
        try:
            model = genai.GenerativeModel('gemini-2.5-flash')
            print(f"[analyze_with_gemini] Model initialized: gemini-2.5-flash")
            
            # Prepare images
            images = []
            for idx, path in enumerate(image_paths):
                print(f"[analyze_with_gemini] Loading image {idx+1}/{len(image_paths)}: {path}")
                if os.path.exists(path):
                    file_size = os.path.getsize(path)
                    print(f"  File exists ({file_size} bytes)")
                    img = Image.open(path)
                    print(f"  Image loaded: {img.size[0]}x{img.size[1]} {img.mode}")
                    images.append(img)
                else:
                    print(f"  WARNING: File does not exist!")
            
            if not images:
                print(f"[analyze_with_gemini] ERROR: No valid images found")
                return {
                    "error": "No valid images found for analysis",
                    "changes_detected": [],
                    "timeline": [],
                    "summary": "Analysis unavailable - no images"
                }
            
            print(f"[analyze_with_gemini] Successfully loaded {len(images)} images")
            
            # Create prompt
            prompt = """
            Analyze these historical satellite images in chronological order.
            Identify:
            1. Major structural changes (buildings, roads, land use)
            2. Timeline of development
            3. Notable patterns or trends
            
            Respond ONLY with valid JSON in this exact format (no markdown, no code blocks):
            {
                "changes_detected": ["change 1", "change 2"],
                "timeline": [{"year": 2018, "observation": "description"}],
                "summary": "overall assessment"
            }
            """
            
            # Generate analysis
            print(f"[analyze_with_gemini] Sending request to Gemini API...")
            response = model.generate_content([prompt] + images)
            print(f"[analyze_with_gemini] Response received")
            
            # Parse response - handle potential markdown wrapping
            response_text = response.text.strip()
            print(f"[analyze_with_gemini] Response length: {len(response_text)} chars")
            print(f"[analyze_with_gemini] First 200 chars: {response_text[:200]}")
            
            # Remove markdown code blocks if present
            if response_text.startswith('```json'):
                print(f"[analyze_with_gemini] Removing ```json wrapper")
                response_text = response_text.replace('```json', '').replace('```', '').strip()
            elif response_text.startswith('```'):
                print(f"[analyze_with_gemini] Removing ``` wrapper")
                response_text = response_text.replace('```', '').strip()
            
            try:
                print(f"[analyze_with_gemini] Parsing JSON...")
                analysis = json.loads(response_text)
                print(f"[analyze_with_gemini] JSON parsed successfully")
            except json.JSONDecodeError as je:
                print(f"[analyze_with_gemini] JSON parsing failed: {str(je)}")
                print(f"[analyze_with_gemini] Raw response: {response_text[:500]}")
                return {
                    "error": "AI response was not valid JSON",
                    "raw_response": response_text[:500],
                    "changes_detected": ["Unable to parse AI response"],
                    "timeline": [],
                    "summary": "AI analysis completed but response format was invalid"
                }
            
            # Ensure required keys exist
            required_keys = ["changes_detected", "timeline", "summary"]
            missing_keys = [key for key in required_keys if key not in analysis]
            
            if missing_keys:
                print(f"[analyze_with_gemini] WARNING: Missing keys: {missing_keys}")
                return {
                    "error": f"AI response missing required fields: {missing_keys}",
                    "changes_detected": analysis.get("changes_detected", []),
                    "timeline": analysis.get("timeline", []),
                    "summary": analysis.get("summary", "Incomplete analysis")
                }
            
            print(f"[analyze_with_gemini] Analysis complete:")
            print(f"  Changes detected: {len(analysis['changes_detected'])}")
            print(f"  Timeline entries: {len(analysis['timeline'])}")
            print(f"  Summary length: {len(analysis['summary'])} chars")
            print(f"{'='*60}\n")
            
            return analysis
            
        except Exception as e:
            print(f"[analyze_with_gemini] EXCEPTION: {type(e).__name__}: {str(e)}")
            print(f"{'='*60}\n")
            return {
                "error": f"AI analysis failed: {str(e)}",
                "changes_detected": [],
                "timeline": [],
                "summary": "Analysis unavailable due to error"
            }
    
    def cleanup_temp_files(self, job_id: str):
        """Clean up temporary files for a job"""
        print(f"\n{'='*60}")
        print(f"[cleanup_temp_files] Cleaning up files for job: {job_id}")
        
        try:
            files_deleted = 0
            for file in self.temp_dir.glob(f"{job_id}_*"):
                print(f"  Deleting: {file.name}")
                file.unlink()
                files_deleted += 1
            
            print(f"[cleanup_temp_files] Deleted {files_deleted} files")
            print(f"{'='*60}\n")
        except Exception as e:
            print(f"[cleanup_temp_files] WARNING: Cleanup failed: {e}")
            print(f"{'='*60}\n")
    
    def _parse_availability_output(self, output: str) -> List[str]:
        """Parse GEHistoricalImagery availability output"""
        print(f"[_parse_availability_output] Parsing output...")
        print(f"  Output length: {len(output)} chars")
        
        dates = []
        
        try:
            # Print first 500 chars for debugging
            print(f"[_parse_availability_output] First 500 chars of output:")
            print(f"--- START OUTPUT ---")
            print(output[:500])
            print(f"--- END OUTPUT ---")
            
            # Split output into lines
            lines = output.strip().split('\n')
            print(f"[_parse_availability_output] Number of lines: {len(lines)}")
            
            # Look for dates in YYYY/MM/DD format
            import re
            date_pattern = r'\d{4}/\d{2}/\d{2}'
            
            for idx, line in enumerate(lines):
                matches = re.findall(date_pattern, line)
                if matches:
                    print(f"  Line {idx}: Found {len(matches)} dates: {matches}")
                    # Convert YYYY/MM/DD to YYYY-MM-DD
                    for match in matches:
                        date_normalized = match.replace('/', '-')
                        dates.append(date_normalized)
            
            # Remove duplicates and sort
            dates = sorted(list(set(dates)))
            print(f"[_parse_availability_output] After deduplication: {len(dates)} unique dates")
            
            if not dates:
                print(f"[_parse_availability_output] ERROR: No dates found in output")
                raise Exception("No imagery dates found for this location")
            
            print(f"[_parse_availability_output] Final result: {dates}")
            return dates
            
        except Exception as e:
            print(f"[_parse_availability_output] EXCEPTION: {type(e).__name__}: {str(e)}")
            raise Exception(f"Failed to parse availability dates: {str(e)}")


class WebhookService:
    """Handle webhook callbacks"""
    
    @staticmethod
    async def send_webhook(url: str, payload: Dict[str, Any]):
        """Send webhook with retry logic"""
        import httpx
        
        print(f"\n{'='*60}")
        print(f"[send_webhook] Sending webhook to: {url}")
        print(f"  Payload keys: {list(payload.keys())}")
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"[send_webhook] Attempt {attempt + 1}/{max_retries}")
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(url, json=payload)
                    print(f"  Response status: {response.status_code}")
                    
                    if response.status_code < 300:
                        print(f"[send_webhook] SUCCESS")
                        print(f"{'='*60}\n")
                        return True
                    else:
                        print(f"  Response body: {response.text[:200]}")
            except Exception as e:
                print(f"  Exception: {type(e).__name__}: {str(e)}")
                if attempt == max_retries - 1:
                    print(f"[send_webhook] FAILED after {max_retries} attempts")
                    print(f"{'='*60}\n")
                    return False
                # Exponential backoff
                wait_time = 2 ** attempt
                print(f"  Waiting {wait_time}s before retry...")
                await asyncio.sleep(wait_time)
        
        print(f"[send_webhook] FAILED")
        print(f"{'='*60}\n")
        return False