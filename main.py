from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import os
from video_stitcher import VideoStitcher
import tempfile
import shutil

app = FastAPI(title="Video Stitcher API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Create a temporary directory for storing uploaded files
TEMP_DIR = "temp_uploads"
os.makedirs(TEMP_DIR, exist_ok=True)

@app.get("/")
async def root():
    return RedirectResponse(url="/static/index.html")

@app.post("/stitch-videos/")
async def stitch_videos(wwe_video: UploadFile = File(...), fan_video: UploadFile = File(...)):
    """
    Stitch two videos together with transitions and commentary
    """
    try:
        # Save uploaded files temporarily
        wwe_path = os.path.join(TEMP_DIR, "wwe_video.mp4")
        fan_path = os.path.join(TEMP_DIR, "fan_video.mp4")
        output_path = os.path.join(TEMP_DIR, "output.mp4")

        # Save uploaded files
        with open(wwe_path, "wb") as buffer:
            shutil.copyfileobj(wwe_video.file, buffer)
        with open(fan_path, "wb") as buffer:
            shutil.copyfileobj(fan_video.file, buffer)

        # Create video stitcher instance
        stitcher = VideoStitcher(wwe_path, fan_path)
        
        # Stitch the videos
        stitcher.stitch_videos(output_path)

        # Return the processed video
        return FileResponse(
            output_path,
            media_type="video/mp4",
            filename="stitched_video.mp4",
            background=None
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Clean up temporary files
        for file in [wwe_path, fan_path, output_path]:
            if os.path.exists(file):
                os.remove(file)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 