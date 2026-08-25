# Copyright (c) 2025 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security
"""
Drawing on a frame must not alter the frame it was given.

The defect
----------
`recognize_faces_in_frame()` drew boxes and name labels straight onto the array
it was handed, then returned that same array as `annotated_frame`. The two were
one object, so no unannotated frame existed anywhere after the call.

The camera crops faces out of that frame to build a person's gallery. Every
stored photograph therefore carried a red rectangle around the face and the word
"Unknown" burned across the chin — visible on the profile cards, where a named
person appeared over a picture labelled "Unknown".

The visible part was the smaller half. **Those images are the training set.**
Encodings for every person were computed from pixels with a filled rectangle
drawn through the lower third of the face, identically on every capture. That is
not a property of the person, and it was present in all of it.

Annotation now happens on a copy, made the first time something is drawn — so a
frame with no faces, which is most of them, still costs nothing.
"""

import numpy as np
import pytest

from backend.core.face_recognition import get_face_manager


@pytest.fixture
def manager():
    return get_face_manager()


def _frame(value=40):
    """A plain frame. Contents do not matter; identity and mutation do."""
    return np.full((240, 320, 3), value, dtype=np.uint8)


class TestTheSourceFrameSurvives:
    def test_a_frame_with_no_faces_is_returned_untouched(self, manager):
        """
        The common case, and the one that must stay cheap. A blank frame has no
        faces, so nothing is drawn and no copy is taken.
        """
        frame = _frame()
        before = frame.copy()

        annotated, faces = manager.recognize_faces_in_frame(frame)

        assert faces == []
        assert np.array_equal(frame, before), "the frame was modified"
        assert annotated is frame, "a copy was taken when nothing was drawn"

    def test_drawing_never_writes_to_the_caller_frame(self, manager, monkeypatch):
        """
        The regression itself.

        Face detection is stubbed so the drawing path runs deterministically —
        the real detector's behaviour on a synthetic image is not the subject,
        and this must hold on any machine.
        """
        frame = _frame()
        before = frame.copy()

        # One face, in coordinates the drawing code will use directly.
        monkeypatch.setattr(
            manager, "known_face_encodings", [], raising=False)
        import backend.core.face_recognition as fr
        # The library is bound as `_face_recognition` in that module.
        monkeypatch.setattr(
            fr._face_recognition, "face_locations",
            lambda *a, **k: [(40, 200, 160, 60)])
        monkeypatch.setattr(
            fr._face_recognition, "face_encodings",
            lambda *a, **k: [np.zeros(128)])

        annotated, faces = manager.recognize_faces_in_frame(frame)

        assert len(faces) == 1, "the stub did not reach the drawing path"
        assert np.array_equal(frame, before), (
            "annotation wrote to the caller's frame — the gallery crops come "
            "from this array, so the drawing would be stored as a photograph "
            "and trained on"
        )
        assert annotated is not frame, "annotated frame must be a separate array"
        assert not np.array_equal(annotated, frame), "nothing was actually drawn"
