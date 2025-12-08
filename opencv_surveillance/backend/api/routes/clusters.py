# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
API routes for face clustering
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List

from backend.database.session import get_db
from backend.core.performance import paginate, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from backend.api.schemas.clustering import (
    ClusterResponse,
    ClusterListResponse,
    ClusterFacesResponse,
    ClusteringRequest,
    ClusteringResponse,
    AssignNameRequest,
    AssignNameResponse,
    MergeClustersRequest,
    MergeClustersResponse,
    DeleteClusterRequest,
    DeleteClusterResponse,
    ClusterStatistics,
)
from backend.core.face_clustering import FaceClusteringService
from backend.core.auth import get_current_active_user
from backend.database.models import User, FaceCluster

router = APIRouter(prefix="/clusters", tags=["face-clustering"])
logger = logging.getLogger(__name__)


@router.post("/cluster", response_model=ClusteringResponse)
def cluster_unknown_faces(
    request: ClusteringRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """
    Cluster all unknown faces using DBSCAN algorithm
    
    This endpoint analyzes all unknown face detections and groups
    similar faces together into clusters for easier identification.
    
    **Algorithm:** DBSCAN (Density-Based Spatial Clustering)
    - **eps:** Maximum distance between faces to be in same cluster (0.4-0.6 typical)
    - **min_samples:** Minimum faces needed to form a cluster (2+ recommended)
    
    **Process:**
    1. Extract face encodings from unknown faces
    2. Calculate distances between all face pairs
    3. Group similar faces into clusters
    4. Compute cluster centroids
    5. Assign representative face to each cluster
    
    **Returns:**
    - Number of clusters created
    - Number of faces clustered
    - Number of faces left as noise (unclustered)
    - Clustering time
    """
    try:
        service = FaceClusteringService(
            eps=request.eps or 0.5,
            min_samples=request.min_samples or 2,
            auto_export_enabled=request.auto_export_enabled if request.auto_export_enabled is not None else True,
            auto_export_threshold=request.auto_export_threshold or 5,
            auto_train_enabled=request.auto_train_enabled if request.auto_train_enabled is not None else True,
            auto_name_enabled=request.auto_name_enabled if request.auto_name_enabled is not None else True,
            cluster_known_faces=request.cluster_known_faces if request.cluster_known_faces is not None else True
        )
        
        result = service.cluster_unknown_faces(db, recalculate=request.recalculate)
        return ClusteringResponse(**result)
        
    except Exception as e:
        logger.error(f"Error clustering faces: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cluster faces: {str(e)}"
        )


@router.get("/", response_model=ClusterListResponse)
def get_all_clusters(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Items per page"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """
    Get all face clusters with pagination

    Performance optimizations:
    - Uses indexed queries on updated_at for sorting
    - Paginated results (default 50, max 1000)
    - Efficient ordering by last updated

    Returns a paginated list of all face clusters, ordered by
    last seen time (most recent first).

    **Query Parameters:**
    - **page:** Page number (default: 1)
    - **page_size:** Items per page (default: 50, max: 1000)

    **Returns:**
    - List of clusters with metadata
    - Total count
    - Pagination info
    """
    try:
        # Build query ordered by most recently updated (uses idx_cluster_updated index)
        query = db.query(FaceCluster).order_by(FaceCluster.updated_at.desc())

        # Apply pagination
        clusters, total, total_pages = paginate(query, page=page, page_size=page_size)

        # Calculate skip for backward compatibility
        skip = (page - 1) * page_size

        return ClusterListResponse(
            clusters=clusters,
            total=total,
            skip=skip,
            limit=page_size
        )

    except Exception as e:
        logger.error(f"Error fetching clusters: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch clusters: {str(e)}"
        )


@router.get("/{cluster_id}", response_model=ClusterResponse)
def get_cluster(
    cluster_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """
    Get a specific cluster by ID
    
    Returns detailed information about a single face cluster.
    
    **Path Parameters:**
    - **cluster_id:** Unique identifier for the cluster
    
    **Returns:**
    - Cluster metadata
    - Face count
    - Representative snapshot
    - Identification status
    """
    service = FaceClusteringService()
    cluster = service.get_cluster_by_id(db, cluster_id)
    
    if not cluster:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cluster {cluster_id} not found"
        )
    
    return cluster


@router.get("/{cluster_id}/faces", response_model=ClusterFacesResponse)
def get_cluster_faces(
    cluster_id: int,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """
    Get all faces in a specific cluster
    
    Returns a paginated list of all face detections that belong
    to the specified cluster.
    
    **Path Parameters:**
    - **cluster_id:** Unique identifier for the cluster
    
    **Query Parameters:**
    - **skip:** Number of records to skip
    - **limit:** Maximum number of records to return
    
    **Returns:**
    - List of face detections with snapshots
    - Total count
    - Pagination info
    """
    service = FaceClusteringService()
    
    # Verify cluster exists
    cluster = service.get_cluster_by_id(db, cluster_id)
    if not cluster:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cluster {cluster_id} not found"
        )
    
    faces = service.get_cluster_faces(db, cluster_id, skip=skip, limit=limit)
    
    return ClusterFacesResponse(
        cluster_id=cluster_id,
        faces=faces,
        total=cluster.face_count,
        skip=skip,
        limit=limit
    )


@router.post("/{cluster_id}/assign-name", response_model=AssignNameResponse)
def assign_name_to_cluster(
    cluster_id: int,
    request: AssignNameRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """
    Assign a name to a cluster
    
    Identifies a cluster by assigning a person name to it.
    All faces in the cluster will be updated with this name.
    Face recognition training will run in the background.
    
    **Path Parameters:**
    - **cluster_id:** Unique identifier for the cluster
    
    **Request Body:**
    - **person_name:** Name to assign to the cluster
    
    **Process:**
    1. Update cluster label
    2. Mark cluster as identified
    3. Update all face detections in cluster with new name
    4. Copy face images to person folder
    5. Trigger background training (non-blocking)
    
    **Returns:**
    - Success status
    - Number of faces updated
    - Confirmation message
    """
    try:
        service = FaceClusteringService()
        result = service.assign_name_to_cluster(db, cluster_id, request.person_name, auto_train=False)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result["message"]
            )
        
        # Schedule background training if images were copied
        if result.get("training_required"):
            def train_in_background():
                try:
                    from backend.core.face_recognition import get_face_manager
                    face_manager = get_face_manager()
                    face_manager.train_face_recognition()
                    logger.info(f"Background training completed after assigning name to cluster {cluster_id}")
                except Exception as e:
                    logger.error(f"Background training failed: {e}")
            
            background_tasks.add_task(train_in_background)
            logger.info(f"Scheduled background training for cluster {cluster_id}")
        
        return AssignNameResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error assigning name to cluster: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to assign name: {str(e)}"
        )


@router.post("/merge", response_model=MergeClustersResponse)
def merge_clusters(
    request: MergeClustersRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """
    Merge multiple clusters into one
    
    Combines multiple face clusters into a single cluster.
    Useful when the same person appears in multiple clusters.
    
    **Request Body:**
    - **cluster_ids:** List of cluster IDs to merge (minimum 2)
    - **new_name:** Optional name for the merged cluster
    
    **Process:**
    1. Validate all clusters exist
    2. Compute new centroid from all faces
    3. Move all faces to target cluster
    4. Update cluster statistics
    5. Delete source clusters
    
    **Returns:**
    - Target cluster ID
    - Number of faces moved
    - Success status
    """
    try:
        service = FaceClusteringService()
        result = service.merge_clusters(db, request.cluster_ids, request.new_name)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )
        
        return MergeClustersResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error merging clusters: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to merge clusters: {str(e)}"
        )


@router.delete("/{cluster_id}", response_model=DeleteClusterResponse)
def delete_cluster(
    cluster_id: int,
    request: DeleteClusterRequest = DeleteClusterRequest(),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """
    Delete a cluster
    
    Removes a face cluster from the system.
    
    **Path Parameters:**
    - **cluster_id:** Unique identifier for the cluster
    
    **Request Body:**
    - **reassign_unknown:** If true, faces are reassigned to "Unknown"
    
    **Process:**
    1. Find cluster
    2. Reassign faces to "Unknown" (if requested)
    3. Delete cluster record
    
    **Returns:**
    - Success status
    - Number of faces affected
    """
    try:
        service = FaceClusteringService()
        result = service.delete_cluster(
            db,
            cluster_id,
            request.reassign_unknown,
            delete_faces=request.delete_faces
        )

        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result["message"]
            )

        return DeleteClusterResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting cluster: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete cluster: {str(e)}"
        )


@router.get("/statistics/summary", response_model=ClusterStatistics)
def get_clustering_statistics(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """
    Get clustering statistics (cached for 3 minutes)

    Returns comprehensive statistics about face clustering.

    **Returns:**
    - Total clusters
    - Identified vs unidentified clusters
    - Total unknown faces
    - Clustered vs unclustered faces
    - Clustering rate (percentage)

    **Performance**: Results are cached for 3 minutes

    **Use Case:**
    Monitor the effectiveness of face clustering and track
    how many unknown faces have been organized into clusters.
    """
    try:
        from backend.core.performance import timed_lru_cache

        @timed_lru_cache(seconds=180, maxsize=4)
        def _get_cached_cluster_stats():
            """Cached helper to reduce database load"""
            service = FaceClusteringService()
            # FIXED: Use context manager to prevent session leak (v3.6.0.1)
            from backend.database.utils import get_db_context
            with get_db_context() as db_local:
                return service.get_statistics(db_local)

        stats = _get_cached_cluster_stats()
        return ClusterStatistics(**stats)

    except Exception as e:
        logger.error(f"Error fetching statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch statistics: {str(e)}"
        )


# Import FaceCluster model for count query
from backend.database.models import FaceCluster
from backend.core.clustering_scheduler import get_clustering_scheduler


@router.get("/scheduler/status")
def get_scheduler_status(current_user = Depends(get_current_active_user)):
    """
    Get clustering scheduler status and statistics

    Returns information about the automated clustering scheduler,
    including whether it's running, last run time, and statistics.
    """
    try:
        scheduler = get_clustering_scheduler()
        return scheduler.get_statistics()
    except Exception as e:
        logger.error(f"Error fetching scheduler status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch scheduler status: {str(e)}"
        )


@router.post("/scheduler/trigger")
async def trigger_manual_clustering(current_user = Depends(get_current_active_user)):
    """
    Manually trigger clustering (bypasses interval check)

    Immediately runs the clustering algorithm on all unclustered
    unknown faces, regardless of the scheduler's interval setting.
    """
    try:
        scheduler = get_clustering_scheduler()
        result = await scheduler.trigger_manual_clustering()
        return result
    except Exception as e:
        logger.error(f"Error triggering manual clustering: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger clustering: {str(e)}"
        )


@router.post("/scheduler/settings")
def update_scheduler_settings(
    auto_enabled: bool = None,
    interval_minutes: int = None,
    min_faces_threshold: int = None,
    current_user = Depends(get_current_active_user)
):
    """
    Update clustering scheduler settings

    Allows configuration of automatic clustering behavior including:
    - Enable/disable auto-clustering
    - Set interval between runs
    - Set minimum faces threshold
    """
    try:
        scheduler = get_clustering_scheduler()
        scheduler.update_settings(
            auto_cluster_enabled=auto_enabled,
            interval_minutes=interval_minutes,
            min_faces_threshold=min_faces_threshold,
        )
        return {"success": True, "settings": scheduler.get_statistics()}
    except Exception as e:
        logger.error(f"Error updating scheduler settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update settings: {str(e)}"
        )
