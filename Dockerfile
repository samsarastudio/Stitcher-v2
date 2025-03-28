FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create directories for temporary uploads and static files with proper permissions
RUN mkdir -p temp output static && \
    chmod -R 777 temp output && \
    chmod -R 755 static

# Set environment variables
ENV PORT=8000
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app
ENV PYTHONIOENCODING=utf-8
ENV TARGET_WIDTH=1280
ENV TARGET_HEIGHT=720
ENV TARGET_FPS=30
ENV VIDEO_BITRATE=2000k
ENV AUDIO_BITRATE=128k
ENV MAX_UPLOAD_SIZE=100
ENV TEMP_DIR=temp
ENV OUTPUT_DIR=output

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application with proper logging
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --log-level info"] 