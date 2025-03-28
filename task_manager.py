import os
import time
from enum import Enum
from typing import Dict, Optional
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
            "error": None
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