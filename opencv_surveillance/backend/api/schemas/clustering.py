# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Pydantic schemas for face clustering API
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ClusterBase(BaseModel):
    """Base schema for a face cluster"""
    label: Optional[str] = Field(None, description="User-assigned label/name")
    is_identified: bool = Field(False, description="Whether cluster has been identified")


class ClusterCreate(ClusterBase):
    """Schema for creating a new cluster"""
    pass


class ClusterUpdate(BaseModel):
    """Schema for updating a cluster"""
    label: Optional[str] = Field(None, description="New label/name for cluster")
    is_identified: Optional[bool] = Field(None, description="Update identification status")


class ClusterResponse(ClusterBase):
    """Schema for cluster response"""
    id: int
    face_count: int
    avg_confidence: Optional[float]
    representative_snapshot_path: Optional[str]
    created_at: datetime
    updated_at: datetime
    last_seen_at: Optional[datetime]
    clustering_algorithm: str
    
    class Config:
        from_attributes = True


class ClusterListResponse(BaseModel):
    """Schema for cluster list response"""
    clusters: List[ClusterResponse]
    total: int
    skip: int
    limit: int


class ClusterFaceResponse(BaseModel):
    """Schema for face in a cluster"""
    id: int
    camera_id: str
    confidence: float
    detected_at: datetime
    snapshot_path: Optional[str]
    location_top: int
    location_right: int
    location_bottom: int
    location_left: int
    
    class Config:
        from_attributes = True


class ClusterFacesResponse(BaseModel):
    """Schema for faces in a cluster response"""
    cluster_id: int
    faces: List[ClusterFaceResponse]
    total: int
    skip: int
    limit: int


class ClusteringRequest(BaseModel):
    """Schema for clustering request"""
    recalculate: bool = Field(False, description="Recalculate clusters from scratch")
    eps: Optional[float] = Field(0.5, description="DBSCAN eps parameter (0.4-0.6 typical)")
    min_samples: Optional[int] = Field(2, description="Minimum faces per cluster")
    auto_export_enabled: Optional[bool] = Field(True, description="Automatically export clusters that hit threshold")
    auto_export_threshold: Optional[int] = Field(5, description="Minimum faces in cluster to trigger auto-export")
    auto_train_enabled: Optional[bool] = Field(True, description="Automatically train model after export")
    auto_name_enabled: Optional[bool] = Field(True, description="Automatically assign names (unknown1, unknown2, etc.) to unknown clusters")
    cluster_known_faces: Optional[bool] = Field(True, description="Whether to cluster known faces (for profile updates)")


class ClusteringResponse(BaseModel):
    """Schema for clustering response"""
    total_unknown_faces: int
    total_known_faces: Optional[int] = Field(0, description="Number of known faces clustered")
    clusters_created: int
    faces_clustered: int
    faces_unclustered: int
    auto_exports: Optional[int] = Field(0, description="Number of clusters auto-exported")
    auto_names: Optional[int] = Field(0, description="Number of clusters auto-named")
    clustering_time: float
    success: bool = True
    message: str


class AssignNameRequest(BaseModel):
    """Schema for assigning name to cluster"""
    person_name: str = Field(..., description="Name to assign to cluster")


class AssignNameResponse(BaseModel):
    """Schema for assign name response"""
    success: bool
    message: str
    faces_updated: int
    images_copied: Optional[int] = Field(None, description="Number of face images copied to person folder")
    images_skipped: Optional[int] = Field(None, description="Number of images skipped (duplicates)")
    person_created: Optional[bool] = Field(None, description="Whether a new person was created in AI & Faces")
    is_merge: Optional[bool] = Field(None, description="Whether this was a merge with an existing person")
    training_required: Optional[bool] = Field(None, description="Whether face recognition training is required")
    training_result: Optional[dict] = Field(None, description="Training result if auto-trained")


class MergeClustersRequest(BaseModel):
    """Schema for merging clusters"""
    cluster_ids: List[int] = Field(..., description="List of cluster IDs to merge")
    new_name: Optional[str] = Field(None, description="Optional name for merged cluster")


class MergeClustersResponse(BaseModel):
    """Schema for merge clusters response"""
    success: bool
    message: str
    target_cluster_id: int
    faces_moved: int


class DeleteClusterRequest(BaseModel):
    """Schema for deleting cluster"""
    reassign_unknown: bool = Field(True, description="Reassign faces to Unknown")
    delete_faces: bool = Field(False, description="Permanently delete face detection events (for test data)")


class DeleteClusterResponse(BaseModel):
    """Schema for delete cluster response"""
    success: bool
    message: str
    faces_affected: int
    faces_deleted: bool = Field(False, description="Whether face events were permanently deleted")


class ClusterStatistics(BaseModel):
    """Schema for clustering statistics"""
    total_clusters: int
    identified_clusters: int
    unidentified_clusters: int
    total_unknown_faces: int
    clustered_faces: int
    unclustered_faces: int
    clustering_rate: float  # Percentage of unknown faces that are clustered
