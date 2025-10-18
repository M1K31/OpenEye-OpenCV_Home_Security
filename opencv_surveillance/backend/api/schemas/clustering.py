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


class ClusteringResponse(BaseModel):
    """Schema for clustering response"""
    total_unknown_faces: int
    clusters_created: int
    faces_clustered: int
    faces_unclustered: int
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


class DeleteClusterResponse(BaseModel):
    """Schema for delete cluster response"""
    success: bool
    message: str
    faces_affected: int


class ClusterStatistics(BaseModel):
    """Schema for clustering statistics"""
    total_clusters: int
    identified_clusters: int
    unidentified_clusters: int
    total_unknown_faces: int
    clustered_faces: int
    unclustered_faces: int
    clustering_rate: float  # Percentage of unknown faces that are clustered
