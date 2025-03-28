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

# Set up logging with more detail
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
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

logger.info(f"Using temporary directory: {TEMP_DIR}")
logger.info(f"Using output directory: {OUTPUT_DIR}")

# Initialize task manager
task_manager = TaskManager(OUTPUT_DIR)

# Maximum upload size (default to 100MB)
MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", "100MB").replace("MB", "")) * 1024 * 1024
logger.info(f"Maximum upload size: {MAX_UPLOAD_SIZE / (1024*1024)}MB")

async def process_video_task(task_id: str, wwe_path: str, fan_path: str):
    """Background task to process videos"""
    try:
        logger.info(f"Starting video processing for task {task_id}")
        logger.info(f"WWE video path: {wwe_path}")
        logger.info(f"Fan video path: {fan_path}")
        
        # Update task status to processing
        task_manager.update_task_status(task_id, TaskStatus.PROCESSING)
        
        # Create video stitcher instance
        logger.info("Creating VideoStitcher instance")
        stitcher = VideoStitcher(wwe_path, fan_path)
        
        # Get output path
        output_path = task_manager.get_output_path(task_id)
        logger.info(f"Output path: {output_path}")
        
        # Process the video
        logger.info("Starting video stitching process")
        stitcher.stitch_videos(output_path)
        
        # Update task status to completed
        logger.info("Video processing completed successfully")
        task_manager.update_task_status(task_id, TaskStatus.COMPLETED, progress=100)
        
    except Exception as e:
        logger.error(f"Error processing video task {task_id}: {str(e)}", exc_info=True)
        task_manager.update_task_status(task_id, TaskStatus.FAILED, error=str(e))
    finally:
        # Clean up temporary files
        for file in [wwe_path, fan_path]:
            if os.path.exists(file):
                try:
                    os.remove(file)
                    logger.info(f"Cleaned up temporary file: {file}")
                except Exception as e:
                    logger.error(f"Error cleaning up temporary file {file}: {e}")

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
        logger.info(f"Received video upload request for task {task_id}")
        logger.info(f"WWE video filename: {wwe_video.filename}")
        logger.info(f"Fan video filename: {fan_video.filename}")
        
        # Validate file sizes
        wwe_video.file.seek(0, 2)  # Seek to end
        fan_video.file.seek(0, 2)  # Seek to end
        
        wwe_size = wwe_video.file.tell()
        fan_size = fan_video.file.tell()
        
        logger.info(f"WWE video size: {wwe_size / (1024*1024):.2f}MB")
        logger.info(f"Fan video size: {fan_size / (1024*1024):.2f}MB")
        
        if wwe_size > MAX_UPLOAD_SIZE or fan_size > MAX_UPLOAD_SIZE:
            error_msg = f"File size exceeds maximum allowed size of {MAX_UPLOAD_SIZE / (1024*1024)}MB"
            logger.error(error_msg)
            raise HTTPException(
                status_code=400,
                detail=error_msg
            )
        
        # Reset file pointers
        wwe_video.file.seek(0)
        fan_video.file.seek(0)
        
        # Save uploaded files temporarily
        wwe_path = os.path.join(TEMP_DIR, f"wwe_{task_id}.mp4")
        fan_path = os.path.join(TEMP_DIR, f"fan_{task_id}.mp4")
        
        logger.info(f"Saving WWE video to: {wwe_path}")
        logger.info(f"Saving fan video to: {fan_path}")
        
        # Save uploaded files
        with open(wwe_path, "wb") as buffer:
            shutil.copyfileobj(wwe_video.file, buffer)
        with open(fan_path, "wb") as buffer:
            shutil.copyfileobj(fan_video.file, buffer)
        
        # Create task
        logger.info("Creating new task")
        task = task_manager.create_task(
            task_id=task_id,
            wwe_filename=wwe_video.filename,
            fan_filename=fan_video.filename
        )
        
        # Add background task
        logger.info("Adding background task")
        background_tasks.add_task(
            process_video_task,
            task_id=task_id,
            wwe_path=wwe_path,
            fan_path=fan_path
        )
        
        response_data = {
            "task_id": task_id,
            "status": task["status"],
            "message": "Video processing started"
        }
        logger.info(f"Returning response: {response_data}")
        return JSONResponse(response_data)
        
    except Exception as e:
        logger.error(f"Error starting video task: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start video processing: {str(e)}"
        )

@app.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Get the status of a specific task"""
    logger.info(f"Getting status for task {task_id}")
    task = task_manager.get_task(task_id)
    if not task:
        logger.warning(f"Task {task_id} not found")
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@app.get("/tasks")
async def get_all_tasks():
    """Get all tasks"""
    logger.info("Getting all tasks")
    return task_manager.get_all_tasks()

@app.get("/download/{task_id}")
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
    
    logger.info(f"Sending file: {output_path}")
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
    logger.info("Starting application cleanup")
    task_manager.cleanup_old_tasks()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 