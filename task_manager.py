import os
import time
from enum import Enum
from typing import Dict, Optional, List
import logging

logger = logging.getLogger(__name__)

class TaskStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class TaskManager:
    def __init__(self, output_dir: str):
        self.tasks: Dict[str, Dict] = {}
        self.output_dir = output_dir
        self.download_history: List[Dict] = []
        os.makedirs(output_dir, exist_ok=True)
        
    def create_task(self, task_id: str, wwe_filename: str, fan_filename: str) -> Dict:
        """Create a new task and return its initial status"""
        task = {
            "id": task_id,
            "status": TaskStatus.PENDING.value,
            "progress": 0,
            "wwe_filename": wwe_filename,
            "fan_filename": fan_filename,
            "output_filename": f"output_{task_id}.mp4",
            "created_at": time.time(),
            "error": None,
            "downloads": 0
        }
        self.tasks[task_id] = task
        logger.info(f"Created new task: {task_id}")
        return task
    
    def update_task_status(self, task_id: str, status: TaskStatus, progress: int = 0, error: Optional[str] = None) -> Dict:
        """Update the status of a task"""
        if task_id not in self.tasks:
            raise KeyError(f"Task {task_id} not found")
            
        task = self.tasks[task_id]
        task["status"] = status.value
        task["progress"] = progress
        if error:
            task["error"] = error
            
        logger.info(f"Updated task {task_id} status to {status.value}")
        return task
    
    def get_task(self, task_id: str) -> Optional[Dict]:
        """Get the current status of a task"""
        return self.tasks.get(task_id)
    
    def get_all_tasks(self) -> list:
        """Get all tasks"""
        return list(self.tasks.values())
    
    def get_output_path(self, task_id: str) -> str:
        """Get the output path for a task's video"""
        return os.path.join(self.output_dir, self.tasks[task_id]["output_filename"])
    
    def record_download(self, task_id: str) -> None:
        """Record a download for a task"""
        if task_id not in self.tasks:
            return
            
        task = self.tasks[task_id]
        task["downloads"] = task.get("downloads", 0) + 1
        
        # Add to download history
        self.download_history.append({
            "task_id": task_id,
            "timestamp": time.time(),
            "filename": task["output_filename"]
        })
        
        # Keep only last 100 downloads
        if len(self.download_history) > 100:
            self.download_history = self.download_history[-100:]
    
    def get_recent_downloads(self, limit: int = 10) -> List[Dict]:
        """Get recent downloads"""
        return sorted(self.download_history, key=lambda x: x["timestamp"], reverse=True)[:limit]
    
    def get_popular_downloads(self, limit: int = 10) -> List[Dict]:
        """Get most downloaded videos"""
        return sorted(
            [task for task in self.tasks.values() if task["status"] == TaskStatus.COMPLETED.value],
            key=lambda x: x.get("downloads", 0),
            reverse=True
        )[:limit]
    
    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """Remove tasks and their output files older than max_age_hours"""
        current_time = time.time()
        for task_id, task in list(self.tasks.items()):
            if current_time - task["created_at"] > max_age_hours * 3600:
                output_path = self.get_output_path(task_id)
                if os.path.exists(output_path):
                    try:
                        os.remove(output_path)
                        logger.info(f"Removed old output file: {output_path}")
                    except Exception as e:
                        logger.error(f"Error removing old output file: {e}")
                del self.tasks[task_id]
                logger.info(f"Removed old task: {task_id}") 