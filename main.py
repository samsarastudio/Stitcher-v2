from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import os
from video_stitcher import VideoStitcher
import tempfile
import shutil
from dotenv import load_dotenv
import logging
import uuid
import asyncio
from task_manager import TaskManager, TaskStatus

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = FastAPI(title="Video Stitcher API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Create directories for temporary and output files
TEMP_DIR = os.getenv("TEMP_DIR", "temp_uploads")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "output_videos")
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Initialize task manager
task_manager = TaskManager(OUTPUT_DIR)

# Maximum upload size (default to 100MB)
MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", "100MB").replace("MB", "")) * 1024 * 1024

async def process_video_task(task_id: str, wwe_path: str, fan_path: str):
    """Background task to process videos"""
    try:
        # Update task status to processing
        task_manager.update_task_status(task_id, TaskStatus.PROCESSING)
        
        # Create video stitcher instance
        stitcher = VideoStitcher(wwe_path, fan_path)
        
        # Get output path
        output_path = task_manager.get_output_path(task_id)
        
        # Process the video
        stitcher.stitch_videos(output_path)
        
        # Update task status to completed
        task_manager.update_task_status(task_id, TaskStatus.COMPLETED, progress=100)
        
    except Exception as e:
        logger.error(f"Error processing video task {task_id}: {str(e)}")
        task_manager.update_task_status(task_id, TaskStatus.FAILED, error=str(e))
    finally:
        # Clean up temporary files
        for file in [wwe_path, fan_path]:
            if os.path.exists(file):
                try:
                    os.remove(file)
                except Exception as e:
                    logger.error(f"Error cleaning up temporary file: {e}")

@app.get("/")
async def root():
    return RedirectResponse(url="/static/index.html")

@app.post("/stitch-videos/")
async def stitch_videos(
    background_tasks: BackgroundTasks,
    wwe_video: UploadFile = File(...),
    fan_video: UploadFile = File(...)
):
    """
    Start a new video stitching task
    """
    task_id = str(uuid.uuid4())
    wwe_path = None
    fan_path = None
    
    try:
        # Validate file sizes
        wwe_video.file.seek(0, 2)  # Seek to end
        fan_video.file.seek(0, 2)  # Seek to end
        
        wwe_size = wwe_video.file.tell()
        fan_size = fan_video.file.tell()
        
        if wwe_size > MAX_UPLOAD_SIZE or fan_size > MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File size exceeds maximum allowed size of {MAX_UPLOAD_SIZE / (1024*1024)}MB"
            )
        
        # Reset file pointers
        wwe_video.file.seek(0)
        fan_video.file.seek(0)
        
        # Save uploaded files temporarily
        wwe_path = os.path.join(TEMP_DIR, f"wwe_{task_id}.mp4")
        fan_path = os.path.join(TEMP_DIR, f"fan_{task_id}.mp4")
        
        # Save uploaded files
        with open(wwe_path, "wb") as buffer:
            shutil.copyfileobj(wwe_video.file, buffer)
        with open(fan_path, "wb") as buffer:
            shutil.copyfileobj(fan_video.file, buffer)
        
        # Create task
        task = task_manager.create_task(
            task_id=task_id,
            wwe_filename=wwe_video.filename,
            fan_filename=fan_video.filename
        )
        
        # Add background task
        background_tasks.add_task(
            process_video_task,
            task_id=task_id,
            wwe_path=wwe_path,
            fan_path=fan_path
        )
        
        return JSONResponse({
            "task_id": task_id,
            "status": task["status"],
            "message": "Video processing started"
        })
        
    except Exception as e:
        logger.error(f"Error starting video task: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start video processing: {str(e)}"
        )

@app.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Get the status of a specific task"""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@app.get("/tasks")
async def get_all_tasks():
    """Get all tasks"""
    return task_manager.get_all_tasks()

@app.get("/download/{task_id}")
async def download_video(task_id: str):
    """Download the processed video"""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task["status"] != TaskStatus.COMPLETED.value:
        raise HTTPException(status_code=400, detail="Video is not ready for download")
    
    output_path = task_manager.get_output_path(task_id)
    if not os.path.exists(output_path):
        raise HTTPException(status_code=404, detail="Video file not found")
    
    return FileResponse(
        output_path,
        media_type="video/mp4",
        filename=f"stitched_video_{task_id}.mp4",
        background=None
    )

# Cleanup old tasks periodically
@app.on_event("startup")
async def startup_event():
    """Clean up old tasks on startup"""
    task_manager.cleanup_old_tasks()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 