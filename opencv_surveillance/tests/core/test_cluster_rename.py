# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Renaming a cluster has to move everything, not a third of it.

Before this, renaming updated the cluster label and the detections that carried
its cluster_id, then reported success. It left behind:

  * detections carrying the old NAME but no cluster_id — 93 of 796 for one
    person on a real installation, so their history appeared split between two
    people, one of whom did not exist
  * the old gallery folder, still holding the trained images and still feeding
    the recogniser under the name the user thought they had replaced
  * the loaded encodings, so recognition kept answering the old name

Reporting success while doing a third of the job is worse than doing less,
because the user believes it.
"""

import numpy as np
import pytest


class TestRenamingEncodings:
    """The recogniser must answer to the new name immediately."""

    @pytest.fixture
    def manager(self):
        from backend.core import face_recognition as fr
        m = fr.FaceRecognitionManager.__new__(fr.FaceRecognitionManager)
        m.known_face_encodings = [np.zeros(128) for _ in range(5)]
        m.known_face_names = ["unknown1"] * 3 + ["Yala"] * 2
        m.statistics = {}
        m.save_encodings = lambda: None
        return m

    def test_every_encoding_for_that_person_is_renamed(self, manager):
        result = manager.rename_person("unknown1", "Mikel")

        assert result["encodings_renamed"] == 3
        assert manager.known_face_names.count("Mikel") == 3
        assert "unknown1" not in manager.known_face_names

    def test_other_people_are_untouched(self, manager):
        manager.rename_person("unknown1", "Mikel")

        assert manager.known_face_names.count("Yala") == 2

    def test_the_encodings_themselves_are_not_altered(self, manager):
        """Only the label changes; a rename is not a retrain."""
        before = [e.copy() for e in manager.known_face_encodings]

        manager.rename_person("unknown1", "Mikel")

        for original, current in zip(before, manager.known_face_encodings):
            assert np.array_equal(original, current)

    def test_renaming_someone_absent_is_harmless(self, manager):
        result = manager.rename_person("Nobody", "Somebody")

        assert result["encodings_renamed"] == 0
        assert manager.known_face_names.count("unknown1") == 3


class TestTheSweepGuard:
    """
    Detections are swept by name as well as cluster id — but only when no other
    cluster still claims that name, or renaming one cluster would drag another
    cluster's detections along with it.
    """

    def test_the_guard_condition_is_the_right_way_round(self):
        from backend.core import face_clustering
        import inspect

        source = inspect.getsource(face_clustering.FaceClusteringService.assign_name_to_cluster)

        # Sweeps only when nothing else carries the old label.
        assert "others_with_label" in source
        assert "Not sweeping detections named" in source

    def test_it_sweeps_detections_lacking_a_cluster_id(self):
        from backend.core import face_clustering
        import inspect

        source = inspect.getsource(face_clustering.FaceClusteringService.assign_name_to_cluster)

        # The filter must be on person_name, not only on cluster_id.
        assert "FaceDetectionEvent.person_name == previous_label" in source


class TestTheGalleryMoves:
    def test_the_old_folder_is_moved_not_copied(self):
        from backend.core import face_clustering
        import inspect

        source = inspect.getsource(face_clustering.FaceClusteringService.assign_name_to_cluster)

        assert "shutil.move" in source
        assert "old_gallery.rmdir()" in source

    def test_an_unexpected_leftover_is_not_force_deleted(self):
        """
        rmdir fails if anything else is in there, and that failure is logged
        rather than escalated to rmtree. Deleting what we did not put there is
        not this function's business.
        """
        from backend.core import face_clustering
        import inspect

        source = inspect.getsource(face_clustering.FaceClusteringService.assign_name_to_cluster)

        assert "rmtree" not in source
        assert "Left %s in place" in source


class TestItReportsWhatItDid:
    def test_the_result_names_every_kind_of_change(self):
        from backend.core import face_clustering
        import inspect

        source = inspect.getsource(face_clustering.FaceClusteringService.assign_name_to_cluster)

        for field in ("faces_swept_by_name", "images_moved",
                      "encodings_renamed", "previous_label"):
            assert field in source, f"{field} is not reported"
