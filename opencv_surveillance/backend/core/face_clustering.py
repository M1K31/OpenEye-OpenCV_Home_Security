# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Face Clustering Service for OpenEye Surveillance System
Implements AI-powered clustering to group similar unknown faces
"""

import logging
import base64
import json
import numpy as np
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from sklearn.cluster import DBSCAN
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from backend.database.models import FaceDetectionEvent, FaceCluster

logger = logging.getLogger(__name__)


class FaceClusteringService:
    """
    Service for clustering unknown faces using machine learning
    Uses DBSCAN algorithm for density-based clustering
    """

    def __init__(self, eps: float = 0.5, min_samples: int = 2):
        """
        Initialize face clustering service
        
        Args:
            eps: Maximum distance between two samples for clustering (0.4-0.6 typical)
            min_samples: Minimum number of samples in a cluster
        """
        self.eps = eps
        self.min_samples = min_samples
        self.statistics = {
            "total_clusters": 0,
            "total_unknown_faces": 0,
            "clustered_faces": 0,
            "unclustered_faces": 0,
            "last_clustering_time": None
        }

    def encode_face_encoding(self, encoding: np.ndarray) -> str:
        """
        Encode numpy array to base64 string for database storage
        
        Args:
            encoding: Face encoding numpy array
            
        Returns:
            Base64 encoded string
        """
        return base64.b64encode(encoding.tobytes()).decode('utf-8')

    def decode_face_encoding(self, encoded: str) -> np.ndarray:
        """
        Decode base64 string back to numpy array
        
        Args:
            encoded: Base64 encoded string
            
        Returns:
            Face encoding numpy array
        """
        decoded = base64.b64decode(encoded.encode('utf-8'))
        return np.frombuffer(decoded, dtype=np.float64)

    def compute_face_distance(self, encoding1: np.ndarray, encoding2: np.ndarray) -> float:
        """
        Compute Euclidean distance between two face encodings
        
        Args:
            encoding1: First face encoding
            encoding2: Second face encoding
            
        Returns:
            Distance value (0.0 = identical, higher = more different)
        """
        return np.linalg.norm(encoding1 - encoding2)

    def get_unknown_faces(self, db: Session, limit: Optional[int] = None) -> List[FaceDetectionEvent]:
        """
        Get all face detections where person_name is 'Unknown' and no cluster assigned
        
        Args:
            db: Database session
            limit: Maximum number of faces to return (None = all)
            
        Returns:
            List of unknown face detection events
        """
        query = db.query(FaceDetectionEvent).filter(
            and_(
                FaceDetectionEvent.person_name == "Unknown",
                FaceDetectionEvent.face_encoding.isnot(None),
                FaceDetectionEvent.cluster_id.is_(None)
            )
        )
        
        if limit:
            query = query.limit(limit)
            
        return query.all()

    def cluster_unknown_faces(self, db: Session, recalculate: bool = False) -> Dict:
        """
        Cluster all unknown faces using DBSCAN algorithm
        
        Args:
            db: Database session
            recalculate: If True, recalculate clusters from scratch
            
        Returns:
            Dictionary with clustering statistics
        """
        logger.info("Starting face clustering process...")
        start_time = datetime.now()

        # Get unknown faces
        if recalculate:
            # Clear existing cluster assignments
            db.query(FaceDetectionEvent).filter(
                FaceDetectionEvent.person_name == "Unknown"
            ).update({"cluster_id": None})
            db.commit()
            logger.info("Cleared existing cluster assignments")

        unknown_faces = self.get_unknown_faces(db)
        
        if len(unknown_faces) < self.min_samples:
            logger.warning(f"Not enough unknown faces to cluster (found {len(unknown_faces)}, need {self.min_samples})")
            return {
                "total_unknown_faces": len(unknown_faces),
                "clusters_created": 0,
                "faces_clustered": 0,
                "faces_unclustered": len(unknown_faces),
                "clustering_time": (datetime.now() - start_time).total_seconds(),
                "message": f"Need at least {self.min_samples} unknown faces to cluster"
            }

        # Extract face encodings
        face_encodings = []
        face_ids = []
        
        for face in unknown_faces:
            try:
                encoding = self.decode_face_encoding(face.face_encoding)
                face_encodings.append(encoding)
                face_ids.append(face.id)
            except Exception as e:
                logger.error(f"Error decoding face encoding for face {face.id}: {e}")
                continue

        if len(face_encodings) < self.min_samples:
            logger.warning(f"Not enough valid face encodings (found {len(face_encodings)})")
            return {
                "total_unknown_faces": len(unknown_faces),
                "clusters_created": 0,
                "faces_clustered": 0,
                "faces_unclustered": len(unknown_faces),
                "clustering_time": (datetime.now() - start_time).total_seconds(),
                "message": "Not enough valid face encodings"
            }

        # Convert to numpy array
        X = np.array(face_encodings)
        
        logger.info(f"Clustering {len(face_encodings)} face encodings with DBSCAN (eps={self.eps}, min_samples={self.min_samples})")
        
        # Perform DBSCAN clustering
        clustering = DBSCAN(eps=self.eps, min_samples=self.min_samples, metric='euclidean')
        labels = clustering.fit_predict(X)
        
        # Get unique cluster labels (excluding noise label -1)
        unique_labels = set(labels)
        noise_count = list(labels).count(-1)
        cluster_labels = [l for l in unique_labels if l != -1]
        
        logger.info(f"Found {len(cluster_labels)} clusters and {noise_count} noise points")
        
        # Create or update clusters
        clusters_created = 0
        faces_clustered = 0
        
        for cluster_label in cluster_labels:
            # Get all faces in this cluster
            cluster_indices = np.where(labels == cluster_label)[0]
            cluster_face_ids = [face_ids[i] for i in cluster_indices]
            cluster_encodings = [face_encodings[i] for i in cluster_indices]
            
            # Compute centroid (average encoding)
            centroid = np.mean(cluster_encodings, axis=0)
            
            # Find representative face (closest to centroid)
            distances = [self.compute_face_distance(centroid, enc) for enc in cluster_encodings]
            representative_idx = cluster_indices[np.argmin(distances)]
            representative_face = unknown_faces[representative_idx]
            
            # Compute average confidence
            cluster_faces_db = db.query(FaceDetectionEvent).filter(
                FaceDetectionEvent.id.in_(cluster_face_ids)
            ).all()
            avg_confidence = np.mean([f.confidence for f in cluster_faces_db])
            
            # Find last seen time
            last_seen = max([f.detected_at for f in cluster_faces_db])
            
            # Create cluster
            cluster = FaceCluster(
                face_count=len(cluster_face_ids),
                avg_confidence=float(avg_confidence),
                representative_encoding=self.encode_face_encoding(centroid),
                representative_snapshot_path=representative_face.snapshot_path,
                last_seen_at=last_seen,
                clustering_algorithm="dbscan",
                clustering_params=json.dumps({
                    "eps": self.eps,
                    "min_samples": self.min_samples,
                    "metric": "euclidean"
                })
            )
            
            db.add(cluster)
            db.flush()  # Get cluster ID
            
            # Assign faces to cluster
            db.query(FaceDetectionEvent).filter(
                FaceDetectionEvent.id.in_(cluster_face_ids)
            ).update({"cluster_id": cluster.id}, synchronize_session=False)
            
            clusters_created += 1
            faces_clustered += len(cluster_face_ids)
            
            logger.info(f"Created cluster {cluster.id} with {len(cluster_face_ids)} faces")
        
        db.commit()
        
        clustering_time = (datetime.now() - start_time).total_seconds()
        
        # Update statistics
        self.statistics = {
            "total_clusters": clusters_created,
            "total_unknown_faces": len(unknown_faces),
            "clustered_faces": faces_clustered,
            "unclustered_faces": noise_count,
            "last_clustering_time": datetime.now().isoformat()
        }
        
        result = {
            "total_unknown_faces": len(unknown_faces),
            "clusters_created": clusters_created,
            "faces_clustered": faces_clustered,
            "faces_unclustered": noise_count,
            "clustering_time": clustering_time,
            "success": True,
            "message": f"Successfully created {clusters_created} clusters from {faces_clustered} faces"
        }
        
        logger.info(f"Clustering completed: {result}")
        return result

    def get_cluster_by_id(self, db: Session, cluster_id: int) -> Optional[FaceCluster]:
        """
        Get a specific cluster by ID
        
        Args:
            db: Database session
            cluster_id: Cluster ID
            
        Returns:
            FaceCluster or None
        """
        return db.query(FaceCluster).filter(FaceCluster.id == cluster_id).first()

    def get_all_clusters(self, db: Session, skip: int = 0, limit: int = 100) -> List[FaceCluster]:
        """
        Get all face clusters
        
        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of face clusters
        """
        return db.query(FaceCluster).order_by(
            FaceCluster.last_seen_at.desc()
        ).offset(skip).limit(limit).all()

    def get_cluster_faces(self, db: Session, cluster_id: int, skip: int = 0, limit: int = 50) -> List[FaceDetectionEvent]:
        """
        Get all faces in a specific cluster
        
        Args:
            db: Database session
            cluster_id: Cluster ID
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of face detection events
        """
        return db.query(FaceDetectionEvent).filter(
            FaceDetectionEvent.cluster_id == cluster_id
        ).order_by(
            FaceDetectionEvent.detected_at.desc()
        ).offset(skip).limit(limit).all()

    def assign_name_to_cluster(self, db: Session, cluster_id: int, person_name: str) -> Dict:
        """
        Assign a name to a cluster and update all faces in the cluster

        This method:
        1. Creates a person folder in faces/ directory
        2. Copies face snapshots to the person folder
        3. Updates cluster and face records in database
        4. Triggers face recognition retraining

        Args:
            db: Database session
            cluster_id: Cluster ID
            person_name: Name to assign

        Returns:
            Dictionary with operation result
        """
        import os
        import shutil
        from pathlib import Path
        from backend.core.paths import paths
        from backend.core.face_recognition import get_face_manager

        cluster = self.get_cluster_by_id(db, cluster_id)

        if not cluster:
            return {
                "success": False,
                "message": f"Cluster {cluster_id} not found"
            }

        # Sanitize person name
        clean_name = "".join(
            c for c in person_name if c.isalnum() or c in (" ", "_", "-")
        ).strip()

        if not clean_name:
            return {
                "success": False,
                "message": "Invalid person name"
            }

        # Create person directory in faces folder
        person_path = paths.faces_dir / clean_name
        person_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Created/verified person directory: {person_path}")

        # Get all face detections in this cluster
        faces = db.query(FaceDetectionEvent).filter(
            FaceDetectionEvent.cluster_id == cluster_id
        ).all()

        # Copy face snapshots to person folder
        images_copied = 0
        for idx, face in enumerate(faces):
            if face.snapshot_path and os.path.exists(face.snapshot_path):
                try:
                    # Create unique filename: timestamp_camera_idx.jpg
                    timestamp = face.detected_at.strftime("%Y%m%d_%H%M%S")
                    camera_id = face.camera_id.replace("/", "_")
                    dest_filename = f"{timestamp}_{camera_id}_{idx}.jpg"
                    dest_path = person_path / dest_filename

                    # Copy the snapshot
                    shutil.copy2(face.snapshot_path, dest_path)
                    images_copied += 1

                    logger.debug(f"Copied snapshot: {face.snapshot_path} -> {dest_path}")
                except Exception as e:
                    logger.warning(f"Failed to copy snapshot {face.snapshot_path}: {e}")

        logger.info(f"Copied {images_copied} face images to {person_path}")

        # Update cluster in database
        cluster.label = clean_name
        cluster.is_identified = True
        cluster.updated_at = datetime.utcnow()

        # Update all faces in cluster with the new name
        updated_count = db.query(FaceDetectionEvent).filter(
            FaceDetectionEvent.cluster_id == cluster_id
        ).update({
            "person_name": clean_name
        }, synchronize_session=False)

        db.commit()

        # Trigger face recognition retraining
        try:
            face_manager = get_face_manager()
            training_result = face_manager.train_face_recognition()
            logger.info(f"Face recognition retrained: {training_result}")
        except Exception as e:
            logger.error(f"Failed to retrain face recognition: {e}")
            # Don't fail the whole operation if retraining fails

        logger.info(
            f"Assigned name '{clean_name}' to cluster {cluster_id} "
            f"({updated_count} faces updated, {images_copied} images copied)"
        )

        return {
            "success": True,
            "message": f"Assigned name '{clean_name}' to cluster {cluster_id}",
            "faces_updated": updated_count,
            "images_copied": images_copied,
            "person_created": True
        }

    def merge_clusters(self, db: Session, cluster_ids: List[int], new_name: Optional[str] = None) -> Dict:
        """
        Merge multiple clusters into one
        
        Args:
            db: Database session
            cluster_ids: List of cluster IDs to merge
            new_name: Optional name for merged cluster
            
        Returns:
            Dictionary with operation result
        """
        if len(cluster_ids) < 2:
            return {
                "success": False,
                "message": "Need at least 2 clusters to merge"
            }
        
        # Get all clusters
        clusters = db.query(FaceCluster).filter(
            FaceCluster.id.in_(cluster_ids)
        ).all()
        
        if len(clusters) != len(cluster_ids):
            return {
                "success": False,
                "message": "One or more clusters not found"
            }
        
        # Use first cluster as target
        target_cluster = clusters[0]
        source_clusters = clusters[1:]
        
        # Collect all face encodings to recompute centroid
        all_faces = []
        for cluster in clusters:
            faces = self.get_cluster_faces(db, cluster.id, limit=1000)
            all_faces.extend(faces)
        
        # Recompute centroid
        encodings = [self.decode_face_encoding(f.face_encoding) for f in all_faces if f.face_encoding]
        if encodings:
            new_centroid = np.mean(encodings, axis=0)
            target_cluster.representative_encoding = self.encode_face_encoding(new_centroid)
        
        # Update target cluster statistics
        target_cluster.face_count = len(all_faces)
        target_cluster.avg_confidence = np.mean([f.confidence for f in all_faces])
        target_cluster.last_seen_at = max([f.detected_at for f in all_faces])
        target_cluster.updated_at = datetime.utcnow()
        
        if new_name:
            target_cluster.label = new_name
            target_cluster.is_identified = True
        
        # Move all faces from source clusters to target
        total_moved = 0
        for source_cluster in source_clusters:
            moved = db.query(FaceDetectionEvent).filter(
                FaceDetectionEvent.cluster_id == source_cluster.id
            ).update({
                "cluster_id": target_cluster.id
            }, synchronize_session=False)
            total_moved += moved
            
            # Delete source cluster
            db.delete(source_cluster)
        
        db.commit()
        
        logger.info(f"Merged {len(source_clusters)} clusters into cluster {target_cluster.id} ({total_moved} faces)")
        
        return {
            "success": True,
            "message": f"Merged {len(cluster_ids)} clusters into cluster {target_cluster.id}",
            "target_cluster_id": target_cluster.id,
            "faces_moved": total_moved
        }

    def delete_cluster(self, db: Session, cluster_id: int, reassign_unknown: bool = True, delete_faces: bool = False) -> Dict:
        """
        Delete a cluster

        Args:
            db: Database session
            cluster_id: Cluster ID to delete
            reassign_unknown: If True, reassign faces to "Unknown" (ignored if delete_faces=True)
            delete_faces: If True, permanently delete the face detection events

        Returns:
            Dictionary with operation result
        """
        cluster = self.get_cluster_by_id(db, cluster_id)

        if not cluster:
            return {
                "success": False,
                "message": f"Cluster {cluster_id} not found"
            }

        face_count = cluster.face_count

        if delete_faces:
            # Permanently delete face detection events
            db.query(FaceDetectionEvent).filter(
                FaceDetectionEvent.cluster_id == cluster_id
            ).delete(synchronize_session=False)
            logger.info(f"Permanently deleted {face_count} face detection events from cluster {cluster_id}")
        elif reassign_unknown:
            # Reset faces to unknown
            db.query(FaceDetectionEvent).filter(
                FaceDetectionEvent.cluster_id == cluster_id
            ).update({
                "cluster_id": None,
                "person_name": "Unknown"
            }, synchronize_session=False)

        # Delete cluster
        db.delete(cluster)
        db.commit()

        logger.info(f"Deleted cluster {cluster_id} ({face_count} faces)")

        return {
            "success": True,
            "message": f"Deleted cluster {cluster_id}",
            "faces_affected": face_count,
            "faces_deleted": delete_faces
        }

    def get_statistics(self, db: Session) -> Dict:
        """
        Get clustering statistics
        
        Args:
            db: Database session
            
        Returns:
            Dictionary with statistics
        """
        total_clusters = db.query(FaceCluster).count()
        identified_clusters = db.query(FaceCluster).filter(
            FaceCluster.is_identified == True
        ).count()
        unidentified_clusters = total_clusters - identified_clusters
        
        total_unknown = db.query(FaceDetectionEvent).filter(
            FaceDetectionEvent.person_name == "Unknown"
        ).count()
        
        clustered = db.query(FaceDetectionEvent).filter(
            and_(
                FaceDetectionEvent.person_name == "Unknown",
                FaceDetectionEvent.cluster_id.isnot(None)
            )
        ).count()
        
        unclustered = total_unknown - clustered
        
        return {
            "total_clusters": total_clusters,
            "identified_clusters": identified_clusters,
            "unidentified_clusters": unidentified_clusters,
            "total_unknown_faces": total_unknown,
            "clustered_faces": clustered,
            "unclustered_faces": unclustered,
            "clustering_rate": round((clustered / total_unknown * 100) if total_unknown > 0 else 0, 2)
        }
