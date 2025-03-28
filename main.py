from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request
import os
import logging
import uuid
import asyncio
from dotenv import load_dotenv
from task_manager import TaskManager, TaskStatus
from pathlib import Path
import time

# Load environment variables
load_dotenv()

# Set up logging with more detail
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment variables
TEMP_DIR = os.getenv('TEMP_DIR', 'temp')
OUTPUT_DIR = os.getenv('OUTPUT_DIR', 'output')
MAX_UPLOAD_SIZE = int(os.getenv('MAX_UPLOAD_SIZE', '100'))
TARGET_WIDTH = int(os.getenv('TARGET_WIDTH', '1280'))
TARGET_HEIGHT = int(os.getenv('TARGET_HEIGHT', '720'))
TARGET_FPS = int(os.getenv('TARGET_FPS', '30'))
VIDEO_BITRATE = os.getenv('VIDEO_BITRATE', '2000k')
AUDIO_BITRATE = os.getenv('AUDIO_BITRATE', '128k')

# Create FastAPI app
app = FastAPI(
    title="Video Stitcher API",
    description="API for stitching WWE and fan videos together",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create directories
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Initialize task manager
task_manager = TaskManager(OUTPUT_DIR)

# API Version prefix
API_V1_PREFIX = "/api/v1"

# Health and Status Endpoints
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve the dashboard"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/status")
async def health_check():
    """Health check endpoint for Railway - must return 200 for successful deployment"""
    return {"status": "ok"}

# API v1 Endpoints
@app.get(f"{API_V1_PREFIX}/status")
async def api_status():
    """API status endpoint"""
    return {
        "status": "ok",
        "version": "1.0.0",
        "timestamp": time.time()
    }

@app.get(f"{API_V1_PREFIX}/tasks")
async def list_tasks():
    """List all tasks"""
    return task_manager.get_all_tasks()

@app.get(f"{API_V1_PREFIX}/tasks/{{task_id}}")
async def get_task(task_id: str):
    """Get task details"""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@app.get(f"{API_V1_PREFIX}/tasks/{{task_id}}/download")
async def download_video(task_id: str):
    """Download the processed video"""
    logger.info(f"Download request for task {task_id}")
    task = task_manager.get_task(task_id)
    if not task:
        logger.warning(f"Task {task_id} not found")
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task["status"] != TaskStatus.COMPLETED.value:
        logger.warning(f"Task {task_id} is not completed")
        raise HTTPException(status_code=400, detail="Video is not ready for download")
    
    output_path = task_manager.get_output_path(task_id)
    if not os.path.exists(output_path):
        logger.warning(f"Output file not found for task {task_id}")
        raise HTTPException(status_code=404, detail="Video file not found")
    
    # Record the download
    task_manager.record_download(task_id)
    
    logger.info(f"Sending file: {output_path}")
    return FileResponse(
        output_path,
        media_type="video/mp4",
        filename=f"stitched_video_{task_id}.mp4",
        background=None
    )

@app.get(f"{API_V1_PREFIX}/downloads/recent")
async def get_recent_downloads():
    """Get recent downloads"""
    logger.info("Getting recent downloads")
    return task_manager.get_recent_downloads()

@app.get(f"{API_V1_PREFIX}/downloads/popular")
async def get_popular_downloads():
    """Get popular downloads"""
    logger.info("Getting popular downloads")
    return task_manager.get_popular_downloads()

@app.post(f"{API_V1_PREFIX}/stitch")
async def stitch_videos(
    background_tasks: BackgroundTasks,
    wwe_video: UploadFile = File(...),
    fan_video: UploadFile = File(...)
):
    """Upload and stitch two videos together"""
    try:
        # Validate file types
        if not wwe_video.filename.endswith('.mp4') or not fan_video.filename.endswith('.mp4'):
            raise HTTPException(
                status_code=400,
                detail="Only MP4 files are supported"
            )
        
        # Create unique task ID
        task_id = str(uuid.uuid4())
        
        # Create task
        task = task_manager.create_task(task_id, wwe_video.filename, fan_video.filename)
        
        # Save uploaded files
        wwe_path = os.path.join(TEMP_DIR, f"wwe_{task_id}.mp4")
        fan_path = os.path.join(TEMP_DIR, f"fan_{task_id}.mp4")
        
        try:
            # Save WWE video
            with open(wwe_path, "wb") as f:
                content = await wwe_video.read()
                if len(content) > MAX_UPLOAD_SIZE * 1024 * 1024:  # Convert MB to bytes
                    raise HTTPException(
                        status_code=400,
                        detail=f"WWE video exceeds maximum size of {MAX_UPLOAD_SIZE}MB"
                    )
                f.write(content)
            
            # Save fan video
            with open(fan_path, "wb") as f:
                content = await fan_video.read()
                if len(content) > MAX_UPLOAD_SIZE * 1024 * 1024:  # Convert MB to bytes
                    raise HTTPException(
                        status_code=400,
                        detail=f"Fan video exceeds maximum size of {MAX_UPLOAD_SIZE}MB"
                    )
                f.write(content)
            
            # Update task status to processing
            task_manager.update_task_status(task_id, TaskStatus.PROCESSING)
            
            # Add video processing to background tasks
            background_tasks.add_task(
                process_videos,
                task_id,
                wwe_path,
                fan_path,
                os.path.join(OUTPUT_DIR, task["output_filename"])
            )
            
            return task
            
        except Exception as e:
            # Clean up temporary files if they exist
            for path in [wwe_path, fan_path]:
                if os.path.exists(path):
                    os.remove(path)
            raise e
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing videos: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to process videos"
        )

# Background processing function
async def process_videos(task_id: str, wwe_path: str, fan_path: str, output_path: str):
    """Process videos in background"""
    try:
        # Import here to avoid circular imports
        from video_stitcher import VideoStitcher
        
        # Process videos
        stitcher = VideoStitcher(wwe_path, fan_path)
        stitcher.stitch_videos(output_path)
        
        # Update task status to completed
        task_manager.update_task_status(task_id, TaskStatus.COMPLETED)
        
    except Exception as e:
        logger.error(f"Error processing videos: {e}")
        task_manager.update_task_status(task_id, TaskStatus.FAILED, error=str(e))
    finally:
        # Cleanup temporary files
        try:
            os.remove(wwe_path)
            os.remove(fan_path)
        except Exception as e:
            logger.error(f"Error cleaning up temporary files: {e}")

# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    logger.info("Starting up application...")
    
    try:
        # Create directories if they don't exist with proper permissions
        for directory in [TEMP_DIR, OUTPUT_DIR]:
            os.makedirs(directory, exist_ok=True)
            # Ensure directory is writable
            test_file = os.path.join(directory, "test.txt")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            logger.info(f"Directory {directory} is ready")
        
        # Clean up old tasks
        task_manager.cleanup_old_tasks()
        
        logger.info("Application startup complete")
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")
        raise

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 