# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Scheduled Tasks System
Manages scheduled events like model retraining, retroactive face search, and cleanup
"""

import logging
import asyncio
from datetime import datetime, time, timedelta
from typing import Optional, List, Dict, Any, Callable
from enum import Enum
import json

from backend.database.session import SessionLocal
from backend.database.utils import get_db_context
from backend.database.models import FaceDetectionEvent, SystemSettings
from backend.core.face_recognition import get_face_manager
from backend.core.paths import paths

logger = logging.getLogger(__name__)


class TaskType(str, Enum):
    """Types of scheduled tasks"""
    MODEL_RETRAIN = "model_retrain"
    RETROACTIVE_SEARCH = "retroactive_search"
    CLUSTER_CLEANUP = "cluster_cleanup"
    DATABASE_CLEANUP = "database_cleanup"
    SNAPSHOT_CLEANUP = "snapshot_cleanup"


class TaskStatus(str, Enum):
    """Task execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ScheduledTask:
    """Represents a scheduled task"""

    def __init__(
        self,
        task_type: TaskType,
        enabled: bool = True,
        schedule_time: Optional[time] = None,
        interval_hours: Optional[int] = None,
        last_run: Optional[datetime] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.task_type = task_type
        self.enabled = enabled
        self.schedule_time = schedule_time  # Time of day to run (e.g., 3:00 AM)
        self.interval_hours = interval_hours  # Alternative: run every N hours
        self.last_run = last_run
        self.config = config or {}
        self.status = TaskStatus.PENDING
        self.last_result: Optional[Dict[str, Any]] = None

    def should_run(self) -> bool:
        """Check if task should run now"""
        if not self.enabled:
            return False

        now = datetime.now()

        # Check schedule_time (daily at specific time)
        if self.schedule_time:
            if self.last_run:
                # Already ran today?
                if self.last_run.date() == now.date():
                    return False

            # Is it past the scheduled time?
            current_time = now.time()
            if current_time >= self.schedule_time:
                return True

        # Check interval_hours
        if self.interval_hours:
            if self.last_run:
                time_since_last = now - self.last_run
                if time_since_last >= timedelta(hours=self.interval_hours):
                    return True
            else:
                # Never run before, run now
                return True

        return False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "task_type": self.task_type.value,
            "enabled": self.enabled,
            "schedule_time": self.schedule_time.isoformat() if self.schedule_time else None,
            "interval_hours": self.interval_hours,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "config": self.config,
            "status": self.status.value,
            "last_result": self.last_result
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScheduledTask":
        """Create from dictionary"""
        schedule_time = None
        if data.get("schedule_time"):
            schedule_time = time.fromisoformat(data["schedule_time"])

        last_run = None
        if data.get("last_run"):
            last_run = datetime.fromisoformat(data["last_run"])

        task = cls(
            task_type=TaskType(data["task_type"]),
            enabled=data.get("enabled", True),
            schedule_time=schedule_time,
            interval_hours=data.get("interval_hours"),
            last_run=last_run,
            config=data.get("config", {})
        )
        task.status = TaskStatus(data.get("status", "pending"))
        task.last_result = data.get("last_result")
        return task


class ScheduledTasksManager:
    """
    Manages scheduled tasks for OpenEye
    """

    def __init__(self):
        self.tasks: Dict[TaskType, ScheduledTask] = {}
        self.is_running = False
        self.scheduler_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

        # Statistics
        self.statistics = {
            "total_runs": 0,
            "successful_runs": 0,
            "failed_runs": 0,
            "last_check_time": None
        }

        # Initialize default tasks
        self._init_default_tasks()

    def _init_default_tasks(self):
        """Initialize default scheduled tasks"""
        # Model retraining - daily at 3 AM
        self.tasks[TaskType.MODEL_RETRAIN] = ScheduledTask(
            task_type=TaskType.MODEL_RETRAIN,
            enabled=False,  # Disabled by default
            schedule_time=time(3, 0),  # 3:00 AM
            config={
                "min_new_faces": 5,  # Minimum new face images to trigger retrain
                "include_clusters": True,  # Include faces from identified clusters
                "retroactive_search": True  # Run retroactive search after training
            }
        )

        # Retroactive face search - every 6 hours
        self.tasks[TaskType.RETROACTIVE_SEARCH] = ScheduledTask(
            task_type=TaskType.RETROACTIVE_SEARCH,
            enabled=False,
            interval_hours=6,
            config={
                "max_events": 1000,  # Max events to search per run
                "search_unknown_only": False,  # Also re-identify "Unknown" faces
                "hours_back": 24  # How far back to search
            }
        )

        # Cluster cleanup - daily at 4 AM
        self.tasks[TaskType.CLUSTER_CLEANUP] = ScheduledTask(
            task_type=TaskType.CLUSTER_CLEANUP,
            enabled=False,
            schedule_time=time(4, 0),
            config={
                "remove_empty_clusters": True,
                "merge_similar_clusters": False,  # Advanced feature
                "min_cluster_age_days": 7  # Only cleanup clusters older than N days
            }
        )

        # Database cleanup - weekly
        self.tasks[TaskType.DATABASE_CLEANUP] = ScheduledTask(
            task_type=TaskType.DATABASE_CLEANUP,
            enabled=False,
            interval_hours=168,  # Weekly
            config={
                "retention_days": 30,  # Keep events for N days
                "cleanup_motion_events": True,
                "cleanup_face_events": False  # Preserve face events
            }
        )

        # Snapshot cleanup - daily at 5 AM
        self.tasks[TaskType.SNAPSHOT_CLEANUP] = ScheduledTask(
            task_type=TaskType.SNAPSHOT_CLEANUP,
            enabled=False,
            schedule_time=time(5, 0),
            config={
                "retention_days": 7,
                "preserve_face_snapshots": True
            }
        )

    async def start(self):
        """Start the scheduler"""
        if self.is_running:
            logger.warning("Scheduled tasks manager is already running")
            return

        # Load saved settings
        await self._load_settings()

        self.is_running = True
        self.scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("Scheduled tasks manager started")

    async def stop(self):
        """Stop the scheduler"""
        self.is_running = False
        if self.scheduler_task:
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass

        # Save settings before stopping
        await self._save_settings()
        logger.info("Scheduled tasks manager stopped")

    async def _scheduler_loop(self):
        """Main scheduler loop"""
        while self.is_running:
            try:
                self.statistics["last_check_time"] = datetime.now().isoformat()

                # Check each task
                for task_type, task in self.tasks.items():
                    if task.should_run():
                        await self._run_task(task)

                # Check every 5 minutes
                await asyncio.sleep(300)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                await asyncio.sleep(60)

    async def _run_task(self, task: ScheduledTask):
        """Run a specific task"""
        async with self._lock:
            task.status = TaskStatus.RUNNING
            task.last_run = datetime.now()
            self.statistics["total_runs"] += 1

            try:
                logger.info(f"Running scheduled task: {task.task_type.value}")

                if task.task_type == TaskType.MODEL_RETRAIN:
                    result = await self._run_model_retrain(task.config)
                elif task.task_type == TaskType.RETROACTIVE_SEARCH:
                    result = await self._run_retroactive_search(task.config)
                elif task.task_type == TaskType.CLUSTER_CLEANUP:
                    result = await self._run_cluster_cleanup(task.config)
                elif task.task_type == TaskType.DATABASE_CLEANUP:
                    result = await self._run_database_cleanup(task.config)
                elif task.task_type == TaskType.SNAPSHOT_CLEANUP:
                    result = await self._run_snapshot_cleanup(task.config)
                else:
                    result = {"error": "Unknown task type"}

                task.status = TaskStatus.COMPLETED
                task.last_result = result
                self.statistics["successful_runs"] += 1
                logger.info(f"Task {task.task_type.value} completed: {result}")

            except Exception as e:
                task.status = TaskStatus.FAILED
                task.last_result = {"error": str(e)}
                self.statistics["failed_runs"] += 1
                logger.error(f"Task {task.task_type.value} failed: {e}")

            # Save settings after each task
            await self._save_settings()

    async def _run_model_retrain(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Run face recognition model retraining"""
        from backend.core.face_recognition import get_face_manager

        result = {
            "new_faces_added": 0,
            "model_trained": False,
            "retroactive_search_done": False,
            "events_updated": 0
        }

        with get_db_context() as db:
            # Check if there are enough new faces to warrant retraining
            min_new_faces = config.get("min_new_faces", 5)

            # Count new face images in the faces directory
            face_manager = get_face_manager()
            current_encodings = len(face_manager.known_face_encodings)

            # Reload to check for new faces
            face_manager.load_encodings()
            new_encodings = len(face_manager.known_face_encodings)
            new_faces_count = new_encodings - current_encodings

            result["new_faces_added"] = new_faces_count

            if new_faces_count >= min_new_faces or new_faces_count > 0:
                # Training happens during load_encodings
                result["model_trained"] = True
                logger.info(f"Model retrained with {new_faces_count} new face(s)")

                # Run retroactive search if configured
                if config.get("retroactive_search", True):
                    search_result = await self._run_retroactive_search({
                        "search_unknown_only": True,
                        "hours_back": 168,  # 1 week
                        "max_events": 5000
                    })
                    result["retroactive_search_done"] = True
                    result["events_updated"] = search_result.get("events_updated", 0)

        return result

    async def _run_retroactive_search(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Search past events for faces and update identifications
        This is the core retroactive face search feature
        """
        from backend.core.face_recognition import get_face_manager
        import numpy as np

        result = {
            "events_searched": 0,
            "events_updated": 0,
            "new_identifications": {},
            "errors": 0
        }

        with get_db_context() as db:
            face_manager = get_face_manager()

            # Reload known faces to get latest
            face_manager.load_encodings()

            if not face_manager.known_face_encodings:
                result["message"] = "No known faces to search for"
                return result

            # Build query for events to search
            hours_back = config.get("hours_back", 24)
            max_events = config.get("max_events", 1000)
            search_unknown_only = config.get("search_unknown_only", False)

            cutoff_time = datetime.now() - timedelta(hours=hours_back)

            query = db.query(FaceDetectionEvent).filter(
                FaceDetectionEvent.timestamp >= cutoff_time,
                FaceDetectionEvent.face_encoding.isnot(None)
            )

            if search_unknown_only:
                query = query.filter(FaceDetectionEvent.person_name == "Unknown")

            events = query.order_by(FaceDetectionEvent.timestamp.desc()).limit(max_events).all()
            result["events_searched"] = len(events)

            # Check face_recognition availability before entering the loop
            from backend.core.face_recognition import FACE_RECOGNITION_AVAILABLE
            if not FACE_RECOGNITION_AVAILABLE:
                result["message"] = "face_recognition library not installed"
                return result
            import face_recognition as _fr

            # Process each event
            for event in events:
                try:
                    if not event.face_encoding:
                        continue

                    # Decode the stored encoding
                    encoding = np.frombuffer(event.face_encoding, dtype=np.float64)

                    if len(encoding) != 128:
                        continue

                    matches = _fr.compare_faces(
                        face_manager.known_face_encodings,
                        encoding,
                        tolerance=0.6
                    )

                    if True in matches:
                        # Find best match
                        face_distances = _fr.face_distance(
                            face_manager.known_face_encodings,
                            encoding
                        )
                        best_match_index = np.argmin(face_distances)

                        if matches[best_match_index]:
                            new_name = face_manager.known_face_names[best_match_index]
                            old_name = event.person_name

                            # Update if different
                            if old_name != new_name:
                                event.person_name = new_name
                                event.confidence = float(1 - face_distances[best_match_index])
                                result["events_updated"] += 1

                                # Track new identifications
                                if new_name not in result["new_identifications"]:
                                    result["new_identifications"][new_name] = 0
                                result["new_identifications"][new_name] += 1

                except Exception as e:
                    result["errors"] += 1
                    logger.warning(f"Error processing event {event.id}: {e}")

            db.commit()

        return result

    async def _run_cluster_cleanup(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Clean up old/empty face clusters"""
        from backend.database.models import FaceCluster

        result = {
            "clusters_removed": 0,
            "clusters_merged": 0
        }

        with get_db_context() as db:
            min_age_days = config.get("min_cluster_age_days", 7)
            cutoff_date = datetime.now() - timedelta(days=min_age_days)

            if config.get("remove_empty_clusters", True):
                # Find and remove empty clusters
                empty_clusters = db.query(FaceCluster).filter(
                    FaceCluster.created_at < cutoff_date,
                    FaceCluster.face_count == 0
                ).all()

                for cluster in empty_clusters:
                    db.delete(cluster)
                    result["clusters_removed"] += 1

                db.commit()

        return result

    async def _run_database_cleanup(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Clean up old database records"""
        from backend.database.models import MotionDetectionEvent

        result = {
            "motion_events_deleted": 0,
            "face_events_deleted": 0
        }

        with get_db_context() as db:
            retention_days = config.get("retention_days", 30)
            cutoff_date = datetime.now() - timedelta(days=retention_days)

            if config.get("cleanup_motion_events", True):
                deleted = db.query(MotionDetectionEvent).filter(
                    MotionDetectionEvent.timestamp < cutoff_date
                ).delete()
                result["motion_events_deleted"] = deleted

            if config.get("cleanup_face_events", False):
                deleted = db.query(FaceDetectionEvent).filter(
                    FaceDetectionEvent.timestamp < cutoff_date
                ).delete()
                result["face_events_deleted"] = deleted

            db.commit()

        return result

    async def _run_snapshot_cleanup(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Clean up old snapshot files"""
        import os
        from pathlib import Path

        result = {
            "files_deleted": 0,
            "space_freed_mb": 0
        }

        retention_days = config.get("retention_days", 7)
        cutoff_time = datetime.now() - timedelta(days=retention_days)
        cutoff_timestamp = cutoff_time.timestamp()

        snapshots_dir = paths.snapshots_dir
        if not snapshots_dir.exists():
            return result

        # Walk through snapshots directory
        for root, dirs, files in os.walk(snapshots_dir):
            for filename in files:
                filepath = Path(root) / filename
                try:
                    # Check file modification time
                    mtime = filepath.stat().st_mtime
                    if mtime < cutoff_timestamp:
                        # Skip face-related snapshots if configured
                        if config.get("preserve_face_snapshots", True):
                            if "face" in filename.lower():
                                continue

                        size = filepath.stat().st_size
                        filepath.unlink()
                        result["files_deleted"] += 1
                        result["space_freed_mb"] += size / (1024 * 1024)

                except Exception as e:
                    logger.warning(f"Could not delete snapshot {filepath}: {e}")

        result["space_freed_mb"] = round(result["space_freed_mb"], 2)
        return result

    async def trigger_task(self, task_type: TaskType) -> Dict[str, Any]:
        """Manually trigger a task"""
        if task_type not in self.tasks:
            return {"error": f"Unknown task type: {task_type}"}

        task = self.tasks[task_type]
        await self._run_task(task)
        return task.last_result or {}

    def get_task(self, task_type: TaskType) -> Optional[Dict[str, Any]]:
        """Get task info"""
        if task_type in self.tasks:
            return self.tasks[task_type].to_dict()
        return None

    def get_all_tasks(self) -> List[Dict[str, Any]]:
        """Get all tasks info"""
        return [task.to_dict() for task in self.tasks.values()]

    def update_task(
        self,
        task_type: TaskType,
        enabled: Optional[bool] = None,
        schedule_time: Optional[str] = None,
        interval_hours: Optional[int] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Update task settings"""
        if task_type not in self.tasks:
            return False

        task = self.tasks[task_type]

        if enabled is not None:
            task.enabled = enabled

        if schedule_time is not None:
            if schedule_time:
                task.schedule_time = time.fromisoformat(schedule_time)
                task.interval_hours = None  # Clear interval when setting time
            else:
                task.schedule_time = None

        if interval_hours is not None:
            if interval_hours > 0:
                task.interval_hours = interval_hours
                task.schedule_time = None  # Clear time when setting interval
            else:
                task.interval_hours = None

        if config is not None:
            task.config.update(config)

        logger.info(f"Task {task_type.value} settings updated")
        return True

    def get_statistics(self) -> Dict[str, Any]:
        """Get scheduler statistics"""
        return {
            **self.statistics,
            "is_running": self.is_running,
            "tasks_count": len(self.tasks),
            "enabled_tasks": sum(1 for t in self.tasks.values() if t.enabled)
        }

    async def _load_settings(self):
        """Load task settings from database"""
        try:
            with get_db_context() as db:
                setting = db.query(SystemSettings).filter(
                    SystemSettings.setting_key == "scheduled_tasks"
                ).first()

                if setting and setting.setting_value:
                    data = json.loads(setting.setting_value)
                    for task_data in data.get("tasks", []):
                        task_type = TaskType(task_data["task_type"])
                        if task_type in self.tasks:
                            self.tasks[task_type] = ScheduledTask.from_dict(task_data)
                    logger.info("Scheduled tasks settings loaded from database")
        except Exception as e:
            logger.warning(f"Could not load scheduled tasks settings: {e}")

    async def _save_settings(self):
        """Save task settings to database"""
        try:
            with get_db_context() as db:
                data = {
                    "tasks": [task.to_dict() for task in self.tasks.values()],
                    "last_save": datetime.now().isoformat()
                }

                setting = db.query(SystemSettings).filter(
                    SystemSettings.setting_key == "scheduled_tasks"
                ).first()

                if setting:
                    setting.setting_value = json.dumps(data)
                else:
                    setting = SystemSettings(
                        setting_key="scheduled_tasks",
                        setting_value=json.dumps(data),
                        setting_type="json",
                    )
                    db.add(setting)

                db.commit()
        except Exception as e:
            logger.warning(f"Could not save scheduled tasks settings: {e}")


# Global instance
_manager: Optional[ScheduledTasksManager] = None


def get_scheduled_tasks_manager() -> ScheduledTasksManager:
    """Get or create the global scheduled tasks manager instance"""
    global _manager
    if _manager is None:
        _manager = ScheduledTasksManager()
    return _manager
