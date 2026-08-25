# Copyright (c) 2025 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security
"""
Creating a person records the person, not only a folder.

The defect
----------
`POST /faces/people` created a gallery directory and returned a response model.
It never wrote a row to `persons`, so somebody created deliberately by a human
existed on disk and in no table.

Observed on a live install: "Mikayla" had a gallery of four photographs, an
entry on the profiles page — which lists directories, not records — and no row
at all. The profiles page and the database disagreed about who existed.

That is the precise condition the Person model was added to end. Its own
docstring describes a person as previously "emergent from three unlinked places
— a gallery folder name, a cluster's label, and a person_name string repeated on
every detection — with no id and no row".

Reassignment already created the row. This path, where a human deliberately
names someone, did not, so the two disagreed with each other as well.

`origin` and `confirmed_at` are set for the same reason reassignment sets them:
a person created by hand is confirmed from the outset, not a guess awaiting
review. The model records this rather than inferring it, because inferring it
from the name meant somebody genuinely called "unknown5" was treated as a
placeholder forever.
"""

import pytest

from backend.database import models


@pytest.fixture
def person_name(tmp_path):
    """A name unlikely to collide with anything in the test database."""
    return "TestPersonCreationRow"


class TestCreatingAPersonWritesARow:
    def test_a_row_exists_afterwards(self, client, db_session, person_name, admin_auth_headers):
        response = client.post(
            "/api/faces/people", json={"name": person_name}, headers=admin_auth_headers)
        assert response.status_code in (200, 201), response.text

        row = db_session.query(models.Person).filter(
            models.Person.name == person_name).first()

        assert row is not None, (
            "the person was created on disk but not recorded — the profiles "
            "page lists directories, so this gap is invisible there"
        )

    def test_the_person_is_marked_as_created_by_a_human(
            self, client, db_session, person_name, admin_auth_headers):
        """
        Not a guess awaiting review.

        The distinction drives how snapshots are retained: a cluster the system
        named itself keeps every image, because those are exactly the faces
        somebody still has to identify. A person named by hand does not need
        that.
        """
        client.post("/api/faces/people", json={"name": person_name}, headers=admin_auth_headers)

        row = db_session.query(models.Person).filter(
            models.Person.name == person_name).first()

        assert row.origin == "user"
        assert row.confirmed_at is not None, "a deliberate naming is a confirmation"

    def test_creating_the_same_person_twice_does_not_duplicate_the_row(
            self, client, db_session, person_name, admin_auth_headers):
        """
        The endpoint answers an existing person with their details rather than
        an error, so it can be called again. The row must not be written twice —
        the name is unique, so a second insert would fail the request outright.
        """
        client.post("/api/faces/people", json={"name": person_name}, headers=admin_auth_headers)
        second = client.post("/api/faces/people", json={"name": person_name}, headers=admin_auth_headers)

        assert second.status_code in (200, 201, 400), second.text

        rows = db_session.query(models.Person).filter(
            models.Person.name == person_name).all()
        assert len(rows) == 1, f"expected one row, found {len(rows)}"
