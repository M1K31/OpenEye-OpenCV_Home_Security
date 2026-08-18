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


def _resolve_snapshot_path(stored: Optional[str]) -> Optional[str]:
    """
    Resolve a stored snapshot reference to a real filesystem path.

    Snapshots are recorded in the DB as URLs ('/data/snapshots/<file>' or
    '/api/snapshots/<file>') for the frontend; os.path.exists()/shutil.copy2()
    cannot use those (they resolve against the filesystem root). Both URL forms
    map to paths.snapshots_dir. Absolute filesystem paths (legacy) pass through.
    Without this, cluster-based training silently copied ZERO images.
    """
    if not stored:
        return None
    import os
    from backend.core.paths import paths
    for prefix in ("/data/snapshots/", "/api/snapshots/"):
        if stored.startswith(prefix):
            return str(paths.snapshots_dir / os.path.basename(stored))
    if os.path.isabs(stored):
        return stored
    # bare filename or relative path -> assume it lives in the snapshots dir
    return str(paths.snapshots_dir / os.path.basename(stored))


class FaceClusteringService:
    """
    Service for clustering faces (both known and unknown) using machine learning
    Uses DBSCAN algorithm for density-based clustering
    
    Enhanced features:
    - Clusters both known and unknown faces
    - Automatic export when cluster hits threshold
    - Automatic training after export
    - Automatic naming for unknown clusters (unknown1, unknown2, etc.)
    """

    def __init__(
        self, 
        eps: float = 0.5, 
        min_samples: int = 2,
        auto_export_enabled: bool = True,
        auto_export_threshold: int = 5,
        auto_train_enabled: bool = True,
        auto_name_enabled: bool = True,
        cluster_known_faces: bool = True
    ):
        """
        Initialize face clustering service
        
        Args:
            eps: Maximum distance between two samples for clustering (0.4-0.6 typical)
            min_samples: Minimum number of samples in a cluster
            auto_export_enabled: Automatically export clusters that hit threshold
            auto_export_threshold: Minimum faces in cluster to trigger auto-export
            auto_train_enabled: Automatically train model after export
            auto_name_enabled: Automatically assign names (unknown1, unknown2, etc.) to unknown clusters
            cluster_known_faces: Whether to cluster known faces (for profile updates)
        """
        self.eps = eps
        self.min_samples = min_samples

        # Below this distance a newly formed cluster is the same person as an
        # existing one, and joins it instead of becoming a second row.
        #
        # Measured on a real installation carrying two people across five
        # clusters:
        #
        #     same person   0.18, 0.23, 0.28, 0.31
        #     different     0.58, 0.58, 0.60, 0.61, 0.62
        #
        # 0.40 sits in that gap with margin on both sides — comfortably above
        # the worst same-person pair and well below the closest different-person
        # pair. It is deliberately stricter than DBSCAN's eps (0.5), because
        # merging two people is far worse than leaving one person split: a split
        # is visible and repairable, a merge silently teaches one profile
        # another person's face.
        self.merge_distance = 0.40
        self.auto_export_enabled = auto_export_enabled
        self.auto_export_threshold = auto_export_threshold
        self.auto_train_enabled = auto_train_enabled
        self.auto_name_enabled = auto_name_enabled
        self.cluster_known_faces = cluster_known_faces
        self.statistics = {
            "total_clusters": 0,
            "total_unknown_faces": 0,
            "total_known_faces": 0,
            "clustered_faces": 0,
            "unclustered_faces": 0,
            "auto_exports": 0,
            "auto_trains": 0,
            "auto_names": 0,
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

    def get_all_faces_for_clustering(self, db: Session, limit: Optional[int] = None) -> Tuple[List[FaceDetectionEvent], List[FaceDetectionEvent]]:
        """
        Get all faces (both known and unknown) for clustering
        
        Args:
            db: Database session
            limit: Maximum number of faces to return per category (None = all)
            
        Returns:
            Tuple of (unknown_faces, known_faces)
        """
        # Get unknown faces
        unknown_faces = self.get_unknown_faces(db, limit)
        
        # Get known faces if clustering enabled
        known_faces = []
        if self.cluster_known_faces:
            query = db.query(FaceDetectionEvent).filter(
                and_(
                    FaceDetectionEvent.person_name != "Unknown",
                    FaceDetectionEvent.face_encoding.isnot(None),
                    FaceDetectionEvent.cluster_id.is_(None)
                )
            )
            if limit:
                query = query.limit(limit)
            known_faces = query.all()
        
        return unknown_faces, known_faces

    def _get_next_unknown_name(self, db: Session) -> str:
        """
        Get the next available unknown name (unknown1, unknown2, etc.)
        
        Args:
            db: Database session
            
        Returns:
            Next available unknown name
        """
        # Find all existing unknown names
        existing_names = db.query(FaceCluster.label).filter(
            FaceCluster.label.like('unknown%')
        ).all()
        
        # Extract numbers from existing names
        existing_numbers = []
        for (name,) in existing_names:
            if name and name.lower().startswith('unknown'):
                try:
                    num = int(name.lower().replace('unknown', ''))
                    existing_numbers.append(num)
                except ValueError:
                    pass
        
        # Find next available number
        if not existing_numbers:
            return "unknown1"
        
        next_num = max(existing_numbers) + 1
        return f"unknown{next_num}"

    def _find_matching_cluster(self, db: Session, centroid: np.ndarray):
        """
        An existing cluster that is the same person as this centroid, if any.

        Clustering only ever looked at faces that had no cluster yet, and created
        a new row for whatever it found. It never asked whether that person
        already had a cluster — so the same person acquired a new row on every
        run, all inheriting the same auto-assigned name. One installation reached
        five clusters for two people that way.

        Returns the nearest cluster within merge_distance, or None.
        """
        candidates = db.query(FaceCluster).filter(
            FaceCluster.representative_encoding.isnot(None)
        ).all()

        best, best_distance = None, None
        for candidate in candidates:
            try:
                other = self.decode_face_encoding(candidate.representative_encoding)
            except Exception:
                continue
            if other is None or other.shape != centroid.shape:
                continue
            distance = float(np.linalg.norm(centroid - other))
            if best_distance is None or distance < best_distance:
                best, best_distance = candidate, distance

        if best is not None and best_distance is not None and best_distance < self.merge_distance:
            logger.info(
                "Cluster centroid matches existing cluster %s (%s) at distance "
                "%.2f — joining it rather than creating a duplicate",
                best.id, best.label, best_distance,
            )
            return best
        return None

    def consolidate_duplicate_clusters(self, db: Session, dry_run: bool = True) -> Dict:
        """
        Merge clusters that are the same person into one.

        A one-time repair for installations that ran before clustering learned to
        join an existing cluster. Uses the same threshold as that check, so it
        cannot disagree with it.

        Anchored on the largest cluster rather than chained. Chaining — merging A
        into B because they are close, then C into B because C is close to A —
        can walk two genuinely different people together in a few steps. Each
        surviving cluster absorbs only those within merge_distance of ITS OWN
        centroid, so every merge is justified by a direct comparison.

        Args:
            db: database session
            dry_run: when True, report what would happen and change nothing
        """
        clusters = db.query(FaceCluster).filter(
            FaceCluster.representative_encoding.isnot(None)
        ).all()

        decoded = []
        for cluster in clusters:
            try:
                centroid = self.decode_face_encoding(cluster.representative_encoding)
            except Exception as e:
                logger.warning("Skipping cluster %s: unreadable centroid (%s)",
                               cluster.id, e)
                continue
            if centroid is None:
                continue
            decoded.append((cluster, centroid))

        # Largest first: the biggest cluster has the best-supported centroid, so
        # it makes the most trustworthy anchor for everything that joins it.
        decoded.sort(key=lambda pair: -(pair[0].face_count or 0))

        absorbed_ids = set()
        merges = []

        for survivor, survivor_centroid in decoded:
            if survivor.id in absorbed_ids:
                continue
            for other, other_centroid in decoded:
                if other.id == survivor.id or other.id in absorbed_ids:
                    continue
                if other_centroid.shape != survivor_centroid.shape:
                    continue
                distance = float(np.linalg.norm(survivor_centroid - other_centroid))
                if distance < self.merge_distance:
                    absorbed_ids.add(other.id)
                    merges.append({
                        "into": survivor.id,
                        "into_label": survivor.label,
                        "absorbed": other.id,
                        "absorbed_label": other.label,
                        "distance": round(distance, 3),
                        "faces": other.face_count or 0,
                        "label_conflict": bool(
                            survivor.label and other.label
                            and survivor.label != other.label),
                    })

        result = {
            "clusters_examined": len(decoded),
            "merges": merges,
            "clusters_removed": len(absorbed_ids),
            "clusters_remaining": len(decoded) - len(absorbed_ids),
            "dry_run": dry_run,
        }

        if dry_run or not merges:
            return result

        faces_moved = 0
        for merge in merges:
            moved = db.query(FaceDetectionEvent).filter(
                FaceDetectionEvent.cluster_id == merge["absorbed"]
            ).update({"cluster_id": merge["into"]}, synchronize_session=False)
            faces_moved += moved

            survivor = db.query(FaceCluster).filter(
                FaceCluster.id == merge["into"]).first()
            if survivor and survivor.label:
                # The survivor's name wins. Renaming the detections too is the
                # point: leaving them under the absorbed cluster's name is the
                # split this repair exists to remove.
                db.query(FaceDetectionEvent).filter(
                    FaceDetectionEvent.cluster_id == merge["into"]
                ).update({"person_name": survivor.label}, synchronize_session=False)

            db.query(FaceCluster).filter(
                FaceCluster.id == merge["absorbed"]).delete(synchronize_session=False)

        # Recount from the detections themselves rather than by adding the
        # absorbed counts. face_count can already be stale, and adding two stale
        # numbers produces a number that is wrong in a new way.
        for cluster_id in {m["into"] for m in merges}:
            cluster = db.query(FaceCluster).filter(FaceCluster.id == cluster_id).first()
            if cluster:
                cluster.face_count = db.query(FaceDetectionEvent).filter(
                    FaceDetectionEvent.cluster_id == cluster_id).count()
                cluster.updated_at = datetime.utcnow()

        db.commit()
        result["faces_moved"] = faces_moved
        logger.info("Consolidated %s duplicate cluster(s), moving %s face(s)",
                    len(merges), faces_moved)
        return result

    def _export_cluster_faces(self, db: Session, cluster_id: int, person_name: str, update_existing: bool = True) -> Dict:
        """
        Export faces from a cluster to a person folder (internal method)
        
        For known persons, this adds new photos to their existing folder to enhance recognition.
        For unknown persons, this creates a new person folder.
        
        Args:
            db: Database session
            cluster_id: Cluster ID
            person_name: Name for the person folder
            update_existing: If True, adds to existing folder (for known persons). If False, creates new folder.
            
        Returns:
            Dictionary with export results
        """
        import os
        import shutil
        from pathlib import Path
        from backend.core.paths import paths

        cluster = self.get_cluster_by_id(db, cluster_id)
        if not cluster:
            return {"success": False, "message": f"Cluster {cluster_id} not found"}

        # Sanitize person name
        clean_name = "".join(
            c for c in person_name if c.isalnum() or c in (" ", "_", "-")
        ).strip()

        if not clean_name:
            return {"success": False, "message": "Invalid person name"}

        # Create person directory (or use existing)
        person_path = paths.faces_dir / clean_name
        person_path.mkdir(parents=True, exist_ok=True)
        
        # Check if person folder already exists (for known persons)
        is_existing_person = person_path.exists() and any(person_path.iterdir())

        # Get all face detections in this cluster
        faces = db.query(FaceDetectionEvent).filter(
            FaceDetectionEvent.cluster_id == cluster_id
        ).all()

        # Copy face snapshots to person folder
        # For existing persons, only copy if file doesn't already exist (avoid duplicates)
        images_copied = 0
        images_skipped = 0
        existing_files = set()
        
        if is_existing_person and update_existing:
            # Get list of existing files to avoid duplicates
            existing_files = {f.name for f in person_path.iterdir() if f.is_file()}

        for idx, face in enumerate(faces):
            _snap_fs = _resolve_snapshot_path(face.snapshot_path)
            if _snap_fs and os.path.exists(_snap_fs):
                try:
                    timestamp = face.detected_at.strftime("%Y%m%d_%H%M%S")
                    camera_id = face.camera_id.replace("/", "_")
                    dest_filename = f"{timestamp}_{camera_id}_{idx}.jpg"
                    dest_path = person_path / dest_filename
                    
                    # Skip if file already exists (for known persons updating their profile)
                    if dest_filename in existing_files:
                        images_skipped += 1
                        continue
                    
                    shutil.copy2(_snap_fs, dest_path)
                    images_copied += 1
                except Exception as e:
                    logger.warning(f"Failed to copy snapshot {face.snapshot_path}: {e}")

        # Update cluster
        cluster.label = clean_name
        cluster.is_identified = True
        cluster.updated_at = datetime.utcnow()

        # Update all faces in cluster with the new name (if not already set)
        # For known persons, faces might already have the correct name
        updated_count = db.query(FaceDetectionEvent).filter(
            FaceDetectionEvent.cluster_id == cluster_id,
            FaceDetectionEvent.person_name != clean_name
        ).update({
            "person_name": clean_name
        }, synchronize_session=False)

        db.commit()

        logger.info(
            f"Exported cluster {cluster_id} to '{clean_name}': "
            f"{updated_count} faces updated, {images_copied} images copied"
            f"{f', {images_skipped} skipped (duplicates)' if images_skipped > 0 else ''}"
        )

        return {
            "success": True,
            "person_name": clean_name,
            "faces_updated": updated_count,
            "images_copied": images_copied,
            "images_skipped": images_skipped,
            "is_existing_person": is_existing_person
        }

    def _auto_export_and_train_cluster(
        self, 
        db: Session, 
        cluster_id: int, 
        person_name: str, 
        update_existing: bool = True
    ) -> Dict:
        """
        Automatically export cluster and train the model
        
        For known persons, this enhances their profile by adding new photos.
        For unknown persons, this creates a new person and trains the model.
        
        Args:
            db: Database session
            cluster_id: Cluster ID
            person_name: Name for the person
            update_existing: If True, adds to existing folder (for known persons)
            
        Returns:
            Dictionary with results
        """
        from backend.core.face_recognition import get_face_manager

        # Export cluster faces
        export_result = self._export_cluster_faces(db, cluster_id, person_name, update_existing=update_existing)
        
        if not export_result.get("success"):
            return export_result

        # Train the model if enabled
        # Note: This runs during background clustering, but we add timeout protection
        # to prevent indefinite hangs. Training can be triggered manually if needed.
        if self.auto_train_enabled:
            try:
                import os
                import threading
                from backend.core.paths import paths

                face_manager = get_face_manager()

                # Collect paths of newly exported photos for incremental training
                person_dir = paths.faces_dir / person_name
                images_copied = export_result.get("images_copied", 0)

                if images_copied > 0 and person_dir.exists():
                    all_photos = sorted(
                        [
                            str(person_dir / f)
                            for f in os.listdir(person_dir)
                            if f.lower().endswith((".jpg", ".jpeg", ".png"))
                        ],
                        key=os.path.getmtime,
                    )
                    new_photo_paths = all_photos[-images_copied:]
                else:
                    new_photo_paths = []

                training_result = None
                training_error = None

                def train_with_timeout():
                    nonlocal training_result, training_error
                    try:
                        training_result = face_manager.train_from_cluster_export(
                            person_name, new_photo_paths
                        )
                    except Exception as e:
                        training_error = str(e)

                train_thread = threading.Thread(target=train_with_timeout)
                train_thread.start()
                train_thread.join(timeout=120)

                if train_thread.is_alive():
                    logger.warning(f"Cluster training timed out for '{person_name}'")
                    export_result["training_success"] = False
                    export_result["training_error"] = "Training timed out"
                elif training_error:
                    logger.error(f"Failed cluster incremental training: {training_error}")
                    export_result["training_success"] = False
                    export_result["training_error"] = training_error
                else:
                    logger.info(
                        f"Incremental cluster training for '{person_name}': "
                        f"{training_result.get('encodings_added', 0)} new encodings"
                    )
                    export_result["training_result"] = training_result
                    export_result["training_success"] = True
                    export_result["training_source"] = "cluster_incremental"
                    self.statistics["auto_trains"] += 1

                    # Stamp the promotion. This is the only place that can
                    # honestly say the cluster became a profile the recogniser
                    # knows, and the capture policy reads it to decide whether
                    # "already holds enough faces" means "well represented" or
                    # "stuck". Set only on success: a timeout or a training
                    # error leaves it null, which keeps the cluster collecting.
                    cluster = db.query(FaceCluster).filter(
                        FaceCluster.id == cluster_id
                    ).first()
                    if cluster is not None:
                        cluster.trained_at = datetime.utcnow()
                        db.commit()
            except Exception as e:
                logger.error(f"Failed cluster training: {e}")
                export_result["training_success"] = False
                export_result["training_error"] = str(e)

        return export_result

    def cluster_unknown_faces(self, db: Session, recalculate: bool = False) -> Dict:
        """
        Cluster faces (both known and unknown) using DBSCAN algorithm
        
        Enhanced features:
        - Clusters both known and unknown faces
        - Auto-exports clusters that meet threshold
        - Auto-trains model after export
        - Auto-names unknown clusters (unknown1, unknown2, etc.)
        
        Args:
            db: Database session
            recalculate: If True, recalculate clusters from scratch
            
        Returns:
            Dictionary with clustering statistics
        """
        logger.info("Starting face clustering process...")
        start_time = datetime.now()

        # Get all faces for clustering (both known and unknown)
        if recalculate:
            # Clear existing cluster assignments
            db.query(FaceDetectionEvent).filter(
                FaceDetectionEvent.cluster_id.isnot(None)
            ).update({"cluster_id": None})
            db.commit()
            logger.info("Cleared existing cluster assignments")

        unknown_faces, known_faces = self.get_all_faces_for_clustering(db)
        all_faces = unknown_faces + known_faces
        
        total_unknown = len(unknown_faces)
        total_known = len(known_faces)
        
        logger.info(f"Found {total_unknown} unknown faces and {total_known} known faces for clustering")
        
        if len(all_faces) < self.min_samples:
            logger.warning(f"Not enough faces to cluster (found {len(all_faces)}, need {self.min_samples})")
            return {
                "total_unknown_faces": total_unknown,
                "total_known_faces": total_known,
                "clusters_created": 0,
                "faces_clustered": 0,
                "faces_unclustered": len(all_faces),
                "clustering_time": (datetime.now() - start_time).total_seconds(),
                "message": f"Need at least {self.min_samples} faces to cluster"
            }

        # Extract face encodings
        face_encodings = []
        face_ids = []
        
        for face in all_faces:
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
                "total_unknown_faces": total_unknown,
                "total_known_faces": total_known,
                "clusters_created": 0,
                "faces_clustered": 0,
                "faces_unclustered": len(all_faces),
                "clustering_time": (datetime.now() - start_time).total_seconds(),
                "message": "Not enough valid face encodings"
            }

        # Convert to numpy array
        X = np.array(face_encodings)
        
        logger.info(
            f"Clustering {len(face_encodings)} face encodings ({total_unknown} unknown, {total_known} known) "
            f"with DBSCAN (eps={self.eps}, min_samples={self.min_samples})"
        )
        
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
        auto_exports = 0
        auto_names = 0
        clusters_merged = 0
        
        for cluster_label in cluster_labels:
            # Get all faces in this cluster
            cluster_indices = np.where(labels == cluster_label)[0]
            cluster_face_ids = [face_ids[i] for i in cluster_indices]
            cluster_encodings = [face_encodings[i] for i in cluster_indices]
            
            # Compute centroid (average encoding)
            centroid = np.mean(cluster_encodings, axis=0)
            
            # Find representative face (closest to centroid)
            distances = [self.compute_face_distance(centroid, enc) for enc in cluster_encodings]
            min_distance_idx = np.argmin(distances)
            representative_face_idx = cluster_indices[min_distance_idx]
            representative_face = all_faces[representative_face_idx]
            
            # Compute average confidence
            cluster_faces_db = db.query(FaceDetectionEvent).filter(
                FaceDetectionEvent.id.in_(cluster_face_ids)
            ).all()
            avg_confidence = np.mean([f.confidence for f in cluster_faces_db])
            
            # Find last seen time
            last_seen = max([f.detected_at for f in cluster_faces_db])
            
            # Determine if cluster is unknown (all faces are "Unknown")
            is_unknown_cluster = all(f.person_name == "Unknown" for f in cluster_faces_db)
            
            # Determine person name for cluster
            if is_unknown_cluster:
                # For unknown clusters, use existing name if already assigned, or get next unknown name
                existing_person_name = cluster_faces_db[0].person_name if cluster_faces_db else "Unknown"
                if existing_person_name == "Unknown" and self.auto_name_enabled:
                    cluster_person_name = self._get_next_unknown_name(db)
                    auto_names += 1
                else:
                    cluster_person_name = existing_person_name
            else:
                # For known clusters, use the most common person name
                from collections import Counter
                person_names = [f.person_name for f in cluster_faces_db if f.person_name != "Unknown"]
                if person_names:
                    cluster_person_name = Counter(person_names).most_common(1)[0][0]
                else:
                    cluster_person_name = "Unknown"
            
            # Join an existing cluster for this person, if there is one.
            #
            # Checked before creating, because the alternative is what produced
            # five clusters for two people: every run made a new row, each
            # inheriting the same name from the faces it contained, and nothing
            # ever noticed they were the same person.
            existing = self._find_matching_cluster(db, centroid)
            if existing is not None:
                db.query(FaceDetectionEvent).filter(
                    FaceDetectionEvent.id.in_(cluster_face_ids)
                ).update({"cluster_id": existing.id}, synchronize_session=False)

                if existing.label:
                    # The established cluster's name wins. These faces are the
                    # same person, and a second name for them is the bug.
                    db.query(FaceDetectionEvent).filter(
                        FaceDetectionEvent.id.in_(cluster_face_ids)
                    ).update({"person_name": existing.label},
                             synchronize_session=False)
                    cluster_person_name = existing.label

                existing.face_count = db.query(FaceDetectionEvent).filter(
                    FaceDetectionEvent.cluster_id == existing.id
                ).count()
                if last_seen and (existing.last_seen_at is None
                                  or last_seen > existing.last_seen_at):
                    existing.last_seen_at = last_seen
                existing.updated_at = datetime.utcnow()

                # Deliberately NOT updating representative_encoding. The
                # established centroid is computed from far more faces than this
                # batch; replacing it with a small sample's centroid would let
                # the cluster drift toward whatever was seen most recently.
                clusters_merged += 1
                faces_clustered += len(cluster_face_ids)
                logger.info(
                    "Merged %s face(s) into existing cluster %s (%s), now %s faces",
                    len(cluster_face_ids), existing.id, existing.label,
                    existing.face_count,
                )

                if (self.auto_export_enabled
                        and len(cluster_face_ids) >= self.auto_export_threshold):
                    try:
                        self._auto_export_and_train_cluster(
                            db, existing.id, cluster_person_name,
                            update_existing=True)
                        auto_exports += 1
                    except Exception as e:
                        logger.error("Auto-export failed for merged cluster: %s", e)
                continue

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
                }),
                label=cluster_person_name if not is_unknown_cluster or self.auto_name_enabled else None,
                is_identified=not is_unknown_cluster
            )
            
            db.add(cluster)
            db.flush()  # Get cluster ID
            
            # Assign faces to cluster
            db.query(FaceDetectionEvent).filter(
                FaceDetectionEvent.id.in_(cluster_face_ids)
            ).update({"cluster_id": cluster.id}, synchronize_session=False)
            
            # If auto-naming enabled for unknown clusters, update face names
            if is_unknown_cluster and self.auto_name_enabled:
                db.query(FaceDetectionEvent).filter(
                    FaceDetectionEvent.id.in_(cluster_face_ids)
                ).update({"person_name": cluster_person_name}, synchronize_session=False)
            
            clusters_created += 1
            faces_clustered += len(cluster_face_ids)
            
            logger.info(
                f"Created cluster {cluster.id} with {len(cluster_face_ids)} faces "
                f"(name: {cluster_person_name}, unknown: {is_unknown_cluster})"
            )
            
            # Auto-export if cluster meets threshold
            # Export both unknown clusters (new persons) and known clusters (profile updates)
            if (self.auto_export_enabled and 
                len(cluster_face_ids) >= self.auto_export_threshold):
                try:
                    # For known persons, update_existing=True adds new photos to existing folder
                    # For unknown persons, update_existing=False creates new folder
                    update_existing = not is_unknown_cluster
                    export_result = self._auto_export_and_train_cluster(
                        db, cluster.id, cluster_person_name, update_existing=update_existing
                    )
                    if export_result.get("success"):
                        auto_exports += 1
                        self.statistics["auto_exports"] = auto_exports
                        cluster_type = "known person update" if not is_unknown_cluster else "new person"
                        logger.info(
                            f"Auto-exported cluster {cluster.id} ({cluster_person_name}, {cluster_type}): "
                            f"{export_result.get('images_copied', 0)} images copied, "
                            f"{export_result.get('images_skipped', 0)} skipped, "
                            f"training: {export_result.get('training_success', False)}"
                        )
                except Exception as e:
                    logger.error(f"Failed to auto-export cluster {cluster.id}: {e}")
        
        db.commit()
        
        clustering_time = (datetime.now() - start_time).total_seconds()
        
        # Update statistics
        self.statistics = {
            "total_clusters": clusters_created,
            "total_unknown_faces": total_unknown,
            "total_known_faces": total_known,
            "clustered_faces": faces_clustered,
            "unclustered_faces": noise_count,
            "auto_exports": auto_exports,
            "auto_trains": self.statistics.get("auto_trains", 0),
            "auto_names": auto_names,
                "clusters_merged": clusters_merged,
            "last_clustering_time": datetime.now().isoformat()
        }
        
        result = {
            "total_unknown_faces": total_unknown,
            "total_known_faces": total_known,
            "clusters_created": clusters_created,
            "faces_clustered": faces_clustered,
            "faces_unclustered": noise_count,
            "auto_exports": auto_exports,
            "auto_names": auto_names,
                "clusters_merged": clusters_merged,
            "clustering_time": clustering_time,
            "success": True,
            "message": f"Successfully created {clusters_created} clusters from {faces_clustered} faces "
                      f"({total_unknown} unknown, {total_known} known). "
                      f"Auto-exported {auto_exports} clusters, auto-named {auto_names} clusters."
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

    def assign_name_to_cluster(self, db: Session, cluster_id: int, person_name: str, auto_train: bool = False) -> Dict:
        """
        Assign a name to a cluster and update all faces in the cluster

        This method:
        1. Creates a person folder in faces/ directory
        2. Copies face snapshots to the person folder
        3. Updates cluster and face records in database
        4. Optionally triggers face recognition retraining

        Args:
            db: Database session
            cluster_id: Cluster ID
            person_name: Name to assign
            auto_train: If True, retrain the model after assignment (default False to prevent freezing)

        Returns:
            Dictionary with operation result including training_required flag
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

        # Check if person folder already exists (merging with existing known person)
        person_path = paths.faces_dir / clean_name
        is_existing_person = person_path.exists() and any(person_path.iterdir()) if person_path.exists() else False
        person_path.mkdir(parents=True, exist_ok=True)

        if is_existing_person:
            logger.info(f"Merging cluster {cluster_id} with existing person '{clean_name}'")
        else:
            logger.info(f"Created person directory: {person_path}")

        # Get all face detections in this cluster
        faces = db.query(FaceDetectionEvent).filter(
            FaceDetectionEvent.cluster_id == cluster_id
        ).all()

        # Get list of existing files to avoid duplicates when merging with existing person
        existing_files = set()
        if is_existing_person:
            existing_files = {f.name for f in person_path.iterdir() if f.is_file()}

        # Copy face snapshots to person folder
        images_copied = 0
        images_skipped = 0
        for idx, face in enumerate(faces):
            _snap_fs = _resolve_snapshot_path(face.snapshot_path)
            if _snap_fs and os.path.exists(_snap_fs):
                try:
                    # Create unique filename: timestamp_camera_idx.jpg
                    timestamp = face.detected_at.strftime("%Y%m%d_%H%M%S")
                    camera_id = face.camera_id.replace("/", "_")
                    dest_filename = f"{timestamp}_{camera_id}_{idx}.jpg"
                    dest_path = person_path / dest_filename

                    # Skip if file already exists (when merging with existing person)
                    if dest_filename in existing_files:
                        images_skipped += 1
                        continue

                    # Copy the snapshot
                    shutil.copy2(_snap_fs, dest_path)
                    images_copied += 1

                    logger.debug(f"Copied snapshot: {face.snapshot_path} -> {dest_path}")
                except Exception as e:
                    logger.warning(f"Failed to copy snapshot {face.snapshot_path}: {e}")

        logger.info(
            f"Copied {images_copied} face images to {person_path}"
            f"{f', {images_skipped} skipped (duplicates)' if images_skipped > 0 else ''}"
        )

        previous_label = cluster.label

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

        # Sweep by NAME as well as by cluster, because a detection can carry the
        # name without carrying the cluster.
        #
        # Renaming used to filter on cluster_id alone, which left every detection
        # whose clustering had not run — 93 of 796 for one person on a real
        # install — sitting under the old name forever. The person's history then
        # appeared split between two people, one of whom did not exist.
        #
        # Guarded: only sweep when no OTHER cluster still claims that name. If
        # two clusters share a label, renaming one must not drag the other's
        # detections along.
        swept_count = 0
        if previous_label and previous_label != clean_name:
            others_with_label = db.query(FaceCluster).filter(
                FaceCluster.label == previous_label,
                FaceCluster.id != cluster_id,
            ).count()
            if others_with_label:
                logger.warning(
                    "Not sweeping detections named '%s': %s other cluster(s) "
                    "still carry that label. Consolidate them first.",
                    previous_label, others_with_label,
                )
            else:
                # or_(IS NULL, != id) rather than just != id.
                #
                # In SQL, NULL != 1 evaluates to NULL, not true, so a row with no
                # cluster is excluded by a plain inequality — and rows with no
                # cluster are precisely the ones this sweep exists to catch. It
                # silently swept nothing on the install that motivated it: 95
                # detections named unknown1, every one of them with a null
                # cluster_id, all skipped by a filter that looked correct.
                from sqlalchemy import or_
                swept_count = db.query(FaceDetectionEvent).filter(
                    FaceDetectionEvent.person_name == previous_label,
                    or_(
                        FaceDetectionEvent.cluster_id.is_(None),
                        FaceDetectionEvent.cluster_id != cluster_id,
                    ),
                ).update({"person_name": clean_name}, synchronize_session=False)

        db.commit()

        # Move the old gallery across rather than leaving a second copy.
        #
        # Only snapshots were copied above, so the images that had already been
        # exported and TRAINED under the old name stayed where they were. The old
        # folder therefore survived every rename — 701 files in one case — still
        # feeding the recogniser under a name the user thought they had replaced,
        # and doubling the disk it occupied.
        images_moved = 0
        if previous_label and previous_label != clean_name:
            old_gallery = paths.faces_dir / previous_label
            if old_gallery.is_dir() and old_gallery.resolve() != person_path.resolve():
                for item in old_gallery.iterdir():
                    if not item.is_file():
                        continue
                    destination = person_path / item.name
                    if destination.exists():
                        # Same photograph under both names; the copy above
                        # already placed it.
                        item.unlink()
                        continue
                    try:
                        shutil.move(str(item), str(destination))
                        images_moved += 1
                    except Exception as e:
                        logger.warning("Could not move %s: %s", item, e)
                try:
                    old_gallery.rmdir()
                    logger.info("Removed the old gallery folder %s", old_gallery)
                except OSError as e:
                    # Left in place rather than forced: something unexpected is
                    # in there, and deleting what we did not put there is not
                    # this function's business.
                    logger.warning("Left %s in place: %s", old_gallery, e)

        # Rename the loaded encodings instead of retraining from scratch.
        #
        # A full retrain re-encodes every photograph of everyone to change one
        # label, and answers with the OLD name until it finishes — which is the
        # window in which someone decides the rename did not work.
        encodings_renamed = 0
        if previous_label and previous_label != clean_name:
            try:
                face_manager = get_face_manager()
                if hasattr(face_manager, "rename_person"):
                    encodings_renamed = face_manager.rename_person(
                        previous_label, clean_name).get("encodings_renamed", 0)
            except Exception as e:
                logger.error("Could not rename encodings: %s", e)

        training_result = None
        training_required = images_copied > 0  # Training needed if images were copied

        # Optionally trigger face recognition retraining (can be slow, caller should use background task)
        if auto_train and training_required:
            try:
                face_manager = get_face_manager()
                training_result = face_manager.train_face_recognition()
                logger.info(f"Face recognition retrained: {training_result}")
            except Exception as e:
                logger.error(f"Failed to retrain face recognition: {e}")
                # Don't fail the whole operation if retraining fails

        merge_message = f"Merged cluster with existing person '{clean_name}'" if is_existing_person else f"Created new person '{clean_name}'"
        logger.info(
            f"Assigned name '{clean_name}' to cluster {cluster_id} "
            f"({updated_count} faces updated, {images_copied} images copied)"
            f"{f', {images_skipped} skipped' if images_skipped > 0 else ''}"
        )

        return {
            "success": True,
            "message": f"{merge_message} from cluster {cluster_id}",
            "faces_updated": updated_count,
            "faces_swept_by_name": swept_count,
            "images_copied": images_copied,
            "images_moved": images_moved,
            "images_skipped": images_skipped,
            "encodings_renamed": encodings_renamed,
            "previous_label": previous_label,
            "person_created": not is_existing_person,
            "is_merge": is_existing_person,
            "training_required": training_required,
            "training_result": training_result
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


# --------------------------------------------------------------------------
# One-off repair, run by hand.
#
#   python -m backend.core.face_clustering consolidate          (preview)
#   python -m backend.core.face_clustering consolidate --apply  (do it)
#
# Not run automatically at startup. It deletes cluster rows, and a repair that
# happens without being asked for is a repair nobody can decline.

def _cli() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Merge duplicate face clusters belonging to the same person.")
    parser.add_argument("command", choices=["consolidate"])
    parser.add_argument("--apply", action="store_true",
                        help="perform the merges (otherwise preview only)")
    args = parser.parse_args()

    from backend.database.utils import get_db_context

    service = FaceClusteringService()
    with get_db_context() as db:
        before = db.query(FaceCluster).count()
        result = service.consolidate_duplicate_clusters(db, dry_run=not args.apply)

    print(f"Clusters examined: {result['clusters_examined']}")
    if not result["merges"]:
        print("No duplicates found — every cluster is a distinct person.")
        return 0

    for merge in result["merges"]:
        conflict = "  ** DIFFERENT LABELS **" if merge["label_conflict"] else ""
        print(f"  cluster {merge['absorbed']} ({merge['absorbed_label']}, "
              f"{merge['faces']} faces) -> cluster {merge['into']} "
              f"({merge['into_label']}) at distance {merge['distance']}{conflict}")

    print(f"\n{before} clusters -> {result['clusters_remaining']}")
    if result["dry_run"]:
        print("Preview only. Nothing was changed. Re-run with --apply.")
    else:
        print(f"Done. {result.get('faces_moved', 0)} detection(s) reassigned.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
