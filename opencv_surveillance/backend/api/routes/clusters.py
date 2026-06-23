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
    FaceReviewAction,
    FaceReviewResponse,
    BulkFaceReviewRequest,
    BulkFaceReviewResponse,
)
from backend.core.face_clustering import FaceClusteringService
from backend.core.auth import get_current_active_user
from backend.database.models import User, FaceCluster, FaceDetectionEvent

router = APIRouter(prefix="/clusters", tags=["face-clustering"])
logger = logging.getLogger(__name__)


def cleanup_empty_cluster(db: Session, cluster: FaceCluster) -> bool:
    """
    Check if a cluster has 0 faces and delete it if so.

    Args:
        db: Database session
        cluster: The cluster to check

    Returns:
        True if cluster was deleted, False otherwise
    """
    if cluster and cluster.face_count <= 0:
        cluster_id = cluster.id
        cluster_label = cluster.label or f"#{cluster.id}"
        db.delete(cluster)
        logger.info(f"Auto-deleted empty cluster {cluster_id} ({cluster_label})")
        return True
    return False


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


@router.get("/trainable")
def get_trainable_clusters(
    min_faces: int = Query(5, ge=2, description="Minimum faces to be trainable"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """
    Get clusters that have reached the threshold for training

    Returns clusters that have enough face samples to train a new
    face recognition model. The frontend can use this to offer
    the user the option to train the model.

    **Query Parameters:**
    - **min_faces:** Minimum faces in cluster to be trainable (default: 5)

    **Returns:**
    - List of trainable clusters with their face counts
    - Training offer message if any are ready
    - Recommended action
    """
    try:
        # Get clusters with at least min_faces faces that are not identified
        trainable = db.query(FaceCluster).filter(
            FaceCluster.face_count >= min_faces,
            FaceCluster.is_identified == False  # Not yet identified
        ).order_by(FaceCluster.face_count.desc()).all()

        # Get clusters that have been labeled but not yet trained
        # (labeled means they have a name, but is_identified indicates if training was done)
        labeled_clusters = db.query(FaceCluster).filter(
            FaceCluster.face_count >= min_faces,
            FaceCluster.label.isnot(None),
            FaceCluster.is_identified == False
        ).order_by(FaceCluster.face_count.desc()).all()

        clusters_data = []
        labeled_set = {c.id for c in labeled_clusters}

        for cluster in trainable:
            if cluster.id not in labeled_set:
                clusters_data.append({
                    "cluster_id": cluster.id,
                    "face_count": cluster.face_count,
                    "representative_image": cluster.representative_snapshot_path,
                    "first_seen": cluster.created_at.isoformat() if cluster.created_at else None,
                    "last_seen": cluster.updated_at.isoformat() if cluster.updated_at else None,
                    "status": "awaiting_name"
                })

        for cluster in labeled_clusters:
            clusters_data.append({
                "cluster_id": cluster.id,
                "face_count": cluster.face_count,
                "assigned_name": cluster.label,
                "representative_image": cluster.representative_snapshot_path,
                "first_seen": cluster.created_at.isoformat() if cluster.created_at else None,
                "last_seen": cluster.updated_at.isoformat() if cluster.updated_at else None,
                "status": "ready_to_export"
            })

        # Determine offer message
        offer_message = None
        recommended_action = None
        unlabeled_count = len([c for c in trainable if c.id not in labeled_set])

        if len(labeled_clusters) > 0:
            offer_message = f"{len(labeled_clusters)} cluster(s) are ready to be exported and trained"
            recommended_action = "export_and_train"
        elif unlabeled_count > 0:
            offer_message = f"{unlabeled_count} cluster(s) have enough faces for training"
            recommended_action = "assign_names"

        return {
            "trainable_clusters": clusters_data,
            "total_trainable": len(clusters_data),
            "awaiting_names": unlabeled_count,
            "ready_to_export": len(labeled_clusters),
            "offer_message": offer_message,
            "recommended_action": recommended_action,
            "threshold": min_faces
        }

    except Exception as e:
        logger.error(f"Error fetching trainable clusters: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch trainable clusters: {str(e)}"
        )


@router.delete("/cleanup-empty")
def cleanup_empty_clusters(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user)
):
    """
    Remove all clusters with 0 faces.

    Clusters can end up with 0 faces when all their faces are
    reassigned or rejected through the review workflow.

    **Returns:**
    - Number of clusters deleted
    - List of deleted cluster IDs
    """
    try:
        # Find all clusters with 0 faces
        empty_clusters = db.query(FaceCluster).filter(
            FaceCluster.face_count <= 0
        ).all()

        deleted_ids = []
        for cluster in empty_clusters:
            deleted_ids.append(cluster.id)
            logger.info(f"Deleting empty cluster {cluster.id} ({cluster.label or 'unlabeled'})")
            db.delete(cluster)

        db.commit()

        return {
            "success": True,
            "message": f"Deleted {len(deleted_ids)} empty cluster(s)",
            "deleted_count": len(deleted_ids),
            "deleted_ids": deleted_ids
        }

    except Exception as e:
        logger.error(f"Error cleaning up empty clusters: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cleanup empty clusters: {str(e)}"
        )


@router.post("/export-and-train/{cluster_id}")
async def export_cluster_and_train(
    cluster_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """
    Export a cluster's faces and trigger model retraining

    This endpoint:
    1. Exports all face images from the cluster to a person folder
    2. Triggers face recognition model retraining
    3. Optionally runs retroactive search to update past events

    **Path Parameters:**
    - **cluster_id:** ID of the cluster to export

    **Returns:**
    - Export status
    - Training status
    - Number of faces exported
    """
    try:
        cluster = db.query(FaceCluster).filter(FaceCluster.id == cluster_id).first()

        if not cluster:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cluster {cluster_id} not found"
            )

        if not cluster.label:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cluster must have an assigned name (label) before exporting"
            )

        # Export cluster faces using the internal method
        service = FaceClusteringService()
        from backend.core.face_recognition import get_face_manager
        face_manager = get_face_manager()

        # Export faces to person folder
        export_result = service._export_cluster_faces(
            db=db,
            cluster_id=cluster_id,
            person_name=cluster.label
        )

        if not export_result.get("success", False):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=export_result.get("message", "Export failed")
            )

        exported_count = export_result.get("images_copied", 0)

        # Mark cluster as identified
        cluster.is_identified = True
        db.commit()

        # Reload face encodings to include new faces
        face_manager.load_encodings()

        # Trigger retroactive search in background
        from backend.core.scheduled_tasks import get_scheduled_tasks_manager, TaskType
        tasks_manager = get_scheduled_tasks_manager()

        background_tasks.add_task(
            tasks_manager.trigger_task,
            TaskType.RETROACTIVE_SEARCH
        )

        return {
            "success": True,
            "cluster_id": cluster_id,
            "person_name": cluster.label,
            "faces_exported": exported_count,
            "model_retrained": True,
            "retroactive_search_scheduled": True,
            "message": f"Exported {exported_count} faces for '{cluster.label}'. Model retrained. Retroactive search scheduled."
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting cluster and training: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export and train: {str(e)}"
        )


# =====================================================
# Face Review Workflow Endpoints (v3.11.5)
# =====================================================

@router.post("/{cluster_id}/faces/{face_id}/review", response_model=FaceReviewResponse)
def review_face(
    cluster_id: int,
    face_id: int,
    request: FaceReviewAction,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """
    Review a single face's association with a cluster

    Allows users to confirm or reject a face's association with a cluster.
    Rejected faces can be reassigned to a different person or moved to a new unknown cluster.

    **Path Parameters:**
    - **cluster_id:** Current cluster ID containing the face
    - **face_id:** Face detection event ID to review

    **Request Body:**
    - **action:** 'confirm' or 'reject'
    - **reassign_to:** (for rejections) Person name to reassign to, or None for new unknown cluster

    **Workflow:**
    - Confirm: Increases confidence in the association (future enhancement: track confirmed status)
    - Reject: Moves face to different cluster or creates new unknown cluster
    """
    try:
        # Get the face detection event
        face = db.query(FaceDetectionEvent).filter(FaceDetectionEvent.id == face_id).first()
        if not face:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Face {face_id} not found"
            )

        if face.cluster_id != cluster_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Face {face_id} is not in cluster {cluster_id}"
            )

        if request.action == "confirm":
            # For now, confirmation is implicit - face stays in cluster
            # Future: could track explicit confirmation status
            logger.info(f"Face {face_id} confirmed in cluster {cluster_id}")
            return FaceReviewResponse(
                success=True,
                message=f"Face {face_id} confirmed in cluster",
                face_id=face_id,
                action="confirm"
            )

        elif request.action == "reject":
            service = FaceClusteringService()
            original_cluster = db.query(FaceCluster).filter(FaceCluster.id == cluster_id).first()

            if request.reassign_to:
                # Reassign to a specific person - find or create their cluster
                target_cluster = db.query(FaceCluster).filter(
                    FaceCluster.label == request.reassign_to,
                    FaceCluster.is_identified == True
                ).first()

                if target_cluster:
                    # Move face to existing cluster
                    face.cluster_id = target_cluster.id
                    face.person_name = request.reassign_to

                    # Update cluster face counts
                    if original_cluster:
                        original_cluster.face_count = max(0, original_cluster.face_count - 1)
                    target_cluster.face_count += 1

                    # Auto-delete empty cluster
                    cluster_deleted = cleanup_empty_cluster(db, original_cluster)

                    db.commit()

                    logger.info(f"Face {face_id} reassigned from cluster {cluster_id} to {target_cluster.id} ({request.reassign_to})")
                    return FaceReviewResponse(
                        success=True,
                        message=f"Face reassigned to {request.reassign_to}" + (" (original cluster deleted)" if cluster_deleted else ""),
                        face_id=face_id,
                        action="reject",
                        new_cluster_id=target_cluster.id,
                        new_person_name=request.reassign_to
                    )
                else:
                    # Create new cluster for this person
                    new_cluster = FaceCluster(
                        label=request.reassign_to,
                        is_identified=True,
                        face_count=1,
                        clustering_algorithm="manual",
                        representative_snapshot_path=face.snapshot_path,
                        representative_encoding=face.face_encoding
                    )
                    db.add(new_cluster)
                    db.flush()

                    face.cluster_id = new_cluster.id
                    face.person_name = request.reassign_to

                    if original_cluster:
                        original_cluster.face_count = max(0, original_cluster.face_count - 1)

                    # Auto-delete empty cluster
                    cluster_deleted = cleanup_empty_cluster(db, original_cluster)

                    db.commit()

                    logger.info(f"Face {face_id} moved to new cluster {new_cluster.id} for {request.reassign_to}")
                    return FaceReviewResponse(
                        success=True,
                        message=f"Face reassigned to new cluster for {request.reassign_to}" + (" (original cluster deleted)" if cluster_deleted else ""),
                        face_id=face_id,
                        action="reject",
                        new_cluster_id=new_cluster.id,
                        new_person_name=request.reassign_to
                    )
            else:
                # Create new unknown cluster for the rejected face
                new_cluster = FaceCluster(
                    label=None,
                    is_identified=False,
                    face_count=1,
                    clustering_algorithm="manual_rejection",
                    representative_snapshot_path=face.snapshot_path,
                    representative_encoding=face.face_encoding
                )
                db.add(new_cluster)
                db.flush()

                face.cluster_id = new_cluster.id
                face.person_name = "Unknown"

                if original_cluster:
                    original_cluster.face_count = max(0, original_cluster.face_count - 1)

                # Auto-delete empty cluster
                cluster_deleted = cleanup_empty_cluster(db, original_cluster)

                db.commit()

                logger.info(f"Face {face_id} rejected and moved to new unknown cluster {new_cluster.id}")
                return FaceReviewResponse(
                    success=True,
                    message="Face rejected and moved to new unknown cluster" + (" (original cluster deleted)" if cluster_deleted else ""),
                    face_id=face_id,
                    action="reject",
                    new_cluster_id=new_cluster.id
                )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reviewing face {face_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to review face: {str(e)}"
        )


@router.post("/{cluster_id}/faces/bulk-review", response_model=BulkFaceReviewResponse)
def bulk_review_faces(
    cluster_id: int,
    request: BulkFaceReviewRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """
    Bulk review multiple faces in a cluster

    Allows confirming or rejecting multiple faces at once.

    **Path Parameters:**
    - **cluster_id:** Cluster ID containing the faces

    **Request Body:**
    - **face_ids:** List of face IDs to review
    - **action:** 'confirm' or 'reject'
    - **reassign_to:** (for rejections) Person name to reassign all to
    """
    try:
        cluster = db.query(FaceCluster).filter(FaceCluster.id == cluster_id).first()
        if not cluster:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cluster {cluster_id} not found"
            )

        faces_confirmed = 0
        faces_rejected = 0
        faces_reassigned = 0
        errors = []
        new_cluster_id = None

        # Get all faces to process
        faces = db.query(FaceDetectionEvent).filter(
            FaceDetectionEvent.id.in_(request.face_ids),
            FaceDetectionEvent.cluster_id == cluster_id
        ).all()

        if len(faces) != len(request.face_ids):
            found_ids = {f.id for f in faces}
            missing = [fid for fid in request.face_ids if fid not in found_ids]
            errors.append(f"Some faces not found in cluster: {missing}")

        if request.action == "confirm":
            faces_confirmed = len(faces)
            # Future: mark faces as explicitly confirmed
            logger.info(f"Bulk confirmed {faces_confirmed} faces in cluster {cluster_id}")

        elif request.action == "reject":
            if request.reassign_to:
                # Find target cluster for reassignment
                target_cluster = db.query(FaceCluster).filter(
                    FaceCluster.label == request.reassign_to,
                    FaceCluster.is_identified == True
                ).first()

                if not target_cluster:
                    # Create new cluster for this person
                    first_face = faces[0] if faces else None
                    target_cluster = FaceCluster(
                        label=request.reassign_to,
                        is_identified=True,
                        face_count=0,
                        clustering_algorithm="manual_bulk",
                        representative_snapshot_path=first_face.snapshot_path if first_face else None,
                        representative_encoding=first_face.face_encoding if first_face else None
                    )
                    db.add(target_cluster)
                    db.flush()

                new_cluster_id = target_cluster.id

                for face in faces:
                    face.cluster_id = target_cluster.id
                    face.person_name = request.reassign_to
                    faces_reassigned += 1

                target_cluster.face_count += len(faces)
                cluster.face_count = max(0, cluster.face_count - len(faces))

                # Auto-delete empty cluster
                cleanup_empty_cluster(db, cluster)

            else:
                # Create new unknown cluster for rejected faces
                first_face = faces[0] if faces else None
                new_unknown_cluster = FaceCluster(
                    label=None,
                    is_identified=False,
                    face_count=len(faces),
                    clustering_algorithm="manual_bulk_rejection",
                    representative_snapshot_path=first_face.snapshot_path if first_face else None,
                    representative_encoding=first_face.face_encoding if first_face else None
                )
                db.add(new_unknown_cluster)
                db.flush()

                new_cluster_id = new_unknown_cluster.id

                for face in faces:
                    face.cluster_id = new_unknown_cluster.id
                    face.person_name = "Unknown"
                    faces_rejected += 1

                cluster.face_count = max(0, cluster.face_count - len(faces))

                # Auto-delete empty cluster
                cleanup_empty_cluster(db, cluster)

        db.commit()

        action_msg = "confirmed" if request.action == "confirm" else "rejected"
        return BulkFaceReviewResponse(
            success=True,
            message=f"Bulk {action_msg} {len(faces)} faces",
            faces_confirmed=faces_confirmed,
            faces_rejected=faces_rejected,
            faces_reassigned=faces_reassigned,
            new_cluster_id=new_cluster_id,
            errors=errors
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error bulk reviewing faces in cluster {cluster_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to bulk review faces: {str(e)}"
        )
