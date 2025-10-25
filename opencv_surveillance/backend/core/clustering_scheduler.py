# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Automated Face Clustering Scheduler
Runs background clustering tasks automatically
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from backend.database.session import SessionLocal
from backend.database.utils import get_db_context
from backend.database.models import FaceDetectionEvent
from backend.core.face_clustering import FaceClusteringService

logger = logging.getLogger(__name__)


class ClusteringScheduler:
    """
    Manages automated face clustering tasks
    """

    def __init__(
        self,
        auto_cluster_enabled: bool = True,
        auto_cluster_interval_minutes: int = 60,
        min_faces_threshold: int = 10,
        eps: float = 0.5,
        min_samples: int = 2,
    ):
        """
        Initialize clustering scheduler

        Args:
            auto_cluster_enabled: Enable automatic clustering
            auto_cluster_interval_minutes: Minutes between clustering runs
            min_faces_threshold: Minimum unknown faces to trigger clustering
            eps: DBSCAN epsilon parameter
            min_samples: DBSCAN min_samples parameter
        """
        self.auto_cluster_enabled = auto_cluster_enabled
        self.interval_minutes = auto_cluster_interval_minutes
        self.min_faces_threshold = min_faces_threshold
        self.eps = eps
        self.min_samples = min_samples

        self.last_run_time: Optional[datetime] = None
        self.is_running = False
        self.task: Optional[asyncio.Task] = None

        self.statistics = {
            "total_runs": 0,
            "successful_runs": 0,
            "failed_runs": 0,
            "total_clusters_created": 0,
            "total_faces_clustered": 0,
            "last_run_time": None,
            "last_run_success": None,
        }

    async def start(self):
        """Start the clustering scheduler"""
        if self.is_running:
            logger.warning("Clustering scheduler is already running")
            return

        self.is_running = True
        self.task = asyncio.create_task(self._run_scheduler())
        logger.info(
            f"Clustering scheduler started (interval: {self.interval_minutes}min, "
            f"threshold: {self.min_faces_threshold} faces)"
        )

    async def stop(self):
        """Stop the clustering scheduler"""
        self.is_running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("Clustering scheduler stopped")

    async def _run_scheduler(self):
        """Main scheduler loop"""
        while self.is_running:
            try:
                # Check if clustering should run
                if await self._should_run_clustering():
                    logger.info("Auto-clustering triggered")
                    await self._run_clustering()

                # Sleep for interval
                await asyncio.sleep(self.interval_minutes * 60)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in clustering scheduler: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying

    async def _should_run_clustering(self) -> bool:
        """
        Check if clustering should run based on configured rules

        Returns:
            True if clustering should run
        """
        if not self.auto_cluster_enabled:
            return False

        # Check if enough time has passed since last run
        if self.last_run_time:
            time_since_last_run = datetime.now() - self.last_run_time
            if time_since_last_run < timedelta(minutes=self.interval_minutes):
                return False

        # Check if there are enough unknown faces to cluster
        # FIXED: Use context manager to prevent session leak (v3.6.0.1)
        with get_db_context() as db:
            unknown_count = (
                db.query(FaceDetectionEvent)
                .filter(
                    FaceDetectionEvent.person_name == "Unknown",
                    FaceDetectionEvent.face_encoding.isnot(None),
                    FaceDetectionEvent.cluster_id.is_(None),
                )
                .count()
            )

            logger.debug(f"Unknown unclustered faces: {unknown_count}")
            return unknown_count >= self.min_faces_threshold

    async def _run_clustering(self):
        """Run the clustering algorithm"""
        # FIXED: Use context manager to prevent session leak (v3.6.0.1)
        try:
            with get_db_context() as db:
                self.statistics["total_runs"] += 1
                self.last_run_time = datetime.now()

                # Run clustering
                service = FaceClusteringService(eps=self.eps, min_samples=self.min_samples)
                result = service.cluster_unknown_faces(db, recalculate=False)

                # Update statistics
                self.statistics["successful_runs"] += 1
                self.statistics["total_clusters_created"] += result.get("clusters_created", 0)
                self.statistics["total_faces_clustered"] += result.get("faces_clustered", 0)
                self.statistics["last_run_time"] = self.last_run_time.isoformat()
                self.statistics["last_run_success"] = True

                logger.info(
                    f"Auto-clustering complete: {result.get('clusters_created', 0)} clusters, "
                    f"{result.get('faces_clustered', 0)} faces clustered"
                )

        except Exception as e:
            self.statistics["failed_runs"] += 1
            self.statistics["last_run_success"] = False
            logger.error(f"Auto-clustering failed: {e}")

    async def trigger_manual_clustering(self) -> dict:
        """
        Manually trigger clustering (bypasses interval check)

        Returns:
            Clustering results
        """
        # FIXED: Use context manager to prevent session leak (v3.6.0.1)
        with get_db_context() as db:
            service = FaceClusteringService(eps=self.eps, min_samples=self.min_samples)
            result = service.cluster_unknown_faces(db, recalculate=False)

            self.last_run_time = datetime.now()
            self.statistics["total_runs"] += 1
            self.statistics["successful_runs"] += 1
            self.statistics["total_clusters_created"] += result.get("clusters_created", 0)
            self.statistics["total_faces_clustered"] += result.get("faces_clustered", 0)

            return result

    def get_statistics(self) -> dict:
        """Get scheduler statistics"""
        return {
            **self.statistics,
            "auto_cluster_enabled": self.auto_cluster_enabled,
            "interval_minutes": self.interval_minutes,
            "min_faces_threshold": self.min_faces_threshold,
            "is_running": self.is_running,
        }

    def update_settings(
        self,
        auto_cluster_enabled: Optional[bool] = None,
        interval_minutes: Optional[int] = None,
        min_faces_threshold: Optional[int] = None,
        eps: Optional[float] = None,
        min_samples: Optional[int] = None,
    ):
        """Update scheduler settings"""
        if auto_cluster_enabled is not None:
            self.auto_cluster_enabled = auto_cluster_enabled
        if interval_minutes is not None:
            self.interval_minutes = max(5, interval_minutes)  # Minimum 5 minutes
        if min_faces_threshold is not None:
            self.min_faces_threshold = max(2, min_faces_threshold)
        if eps is not None:
            self.eps = max(0.3, min(0.7, eps))
        if min_samples is not None:
            self.min_samples = max(2, min_samples)

        logger.info(f"Clustering scheduler settings updated")


# Global instance
_scheduler: Optional[ClusteringScheduler] = None


def get_clustering_scheduler() -> ClusteringScheduler:
    """Get or create the global clustering scheduler instance"""
    global _scheduler
    if _scheduler is None:
        _scheduler = ClusteringScheduler()
    return _scheduler
