# Video Stitcher API

This API allows you to stitch two videos together with transitions and commentary. It's built with FastAPI and can be deployed to Render.

## Features

- Upload two videos (WWE and fan videos)
- Stitch videos together with smooth transitions
- Add commentary from the fan video
- Automatic cleanup of temporary files

## Local Development

1. Clone the repository
2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the application:
   ```bash
   uvicorn main:app --reload
   ```

## API Endpoints

### POST /stitch-videos/
Upload two videos to be stitched together.

**Request:**
- Form data with two files:
  - `wwe_video`: The main WWE video file
  - `fan_video`: The fan video file with commentary

**Response:**
- The processed video file

### GET /
Welcome message

## Deployment to Render

1. Push your code to a Git repository
2. Create a new Web Service on Render
3. Connect your repository
4. Configure the service:
   - Build Command: `docker build -t video-stitcher .`
   - Start Command: `docker run -p 8000:8000 video-stitcher`
   - Environment Variables: None required

## Notes

- The API uses temporary storage for processing videos
- Maximum file size is limited by your Render plan
- Processing time depends on video length and complexity #   S t i t c h e r - v 2  
 