# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Tests for relocating an installation's storage.

This is the module where a bug loses a user's recordings, so the assertions are
mostly about what is still on disk afterwards rather than about return values.
The two rules under test throughout: never delete before verifying, and refuse
rather than half-finish.
"""

import os
import types
from pathlib import Path

import pytest

from backend.core import storage_migration as sm


def _tree(root: Path, files: dict) -> Path:
    """Create a directory tree from {relative path: contents}."""
    for relative, content in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content if isinstance(content, bytes) else content.encode())
    return root


def _paths_stub(**kwargs):
    """Stand-in for PathManager with only the attributes the planner reads."""
    defaults = {"faces_dir": None, "recordings_dir": None,
                "snapshots_dir": None, "thumbnails_dir": None}
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


@pytest.fixture
def roots(tmp_path):
    app_root = tmp_path / "app"
    data_root = tmp_path / "data-root"
    app_root.mkdir()
    return types.SimpleNamespace(app=app_root, data=data_root, tmp=tmp_path)


# ------------------------------------------------------------------ planning

class TestPlanning:
    def test_finds_media_beside_the_code(self, roots):
        _tree(roots.app, {"faces/Mikel/a.jpg": b"x", "recordings/clip.mp4": b"yy"})

        plan = sm.build_plan(data_root=roots.data, app_root=roots.app,
                             current_paths=_paths_stub(), database_path=None)

        labels = {i.label for i in plan.items}
        assert labels == {"faces", "recordings"}
        assert plan.total_files == 2

    def test_finds_media_the_environment_pointed_elsewhere(self, roots):
        """
        The case that motivated this: snapshots were neither under the data root
        nor beside the code, but at a third location the environment named.
        """
        elsewhere = _tree(roots.tmp / "elsewhere", {"snap1.jpg": b"x", "snap2.jpg": b"y"})

        plan = sm.build_plan(
            data_root=roots.data, app_root=roots.app,
            current_paths=_paths_stub(snapshots_dir=elsewhere), database_path=None,
        )

        item = next(i for i in plan.items if i.label == "snapshots")
        assert item.source == elsewhere
        assert item.destination == roots.data / "data" / "snapshots"

    def test_ignores_media_already_under_the_data_root(self, roots):
        _tree(roots.data, {"faces/Mikel/a.jpg": b"x"})

        plan = sm.build_plan(data_root=roots.data, app_root=roots.app,
                             current_paths=_paths_stub(faces_dir=roots.data / "faces"),
                             database_path=None)

        assert [i.label for i in plan.items] == []

    def test_ignores_empty_directories(self, roots):
        (roots.app / "faces").mkdir()

        plan = sm.build_plan(data_root=roots.data, app_root=roots.app,
                             current_paths=_paths_stub(), database_path=None)

        assert plan.is_noop

    def test_a_source_checkout_is_never_migrated(self, roots):
        """Data beside the code is correct for a checkout, not a problem."""
        _tree(roots.app, {"faces/a.jpg": b"x"})

        plan = sm.build_plan(data_root=roots.app, app_root=roots.app,
                             current_paths=_paths_stub(), database_path=None)

        assert plan.is_noop

    def test_database_sidecars_travel_with_it(self, roots):
        for suffix in ("", "-wal", "-shm"):
            (roots.app / f"surveillance.db{suffix}").write_bytes(b"db")

        plan = sm.build_plan(data_root=roots.data, app_root=roots.app,
                             current_paths=_paths_stub(),
                             database_path=roots.app / "surveillance.db")

        assert {i.label for i in plan.items} == {"database", "database-wal", "database-shm"}

    def test_explicit_no_database_is_not_treated_as_autodetect(self, roots):
        """
        database_path=None used to mean both "none" and "work it out", so a
        caller saying there was no database silently got the live one instead —
        which is how this planner tried to move the developer's own database
        into a temporary directory.
        """
        _tree(roots.app, {"faces/a.jpg": b"x"})

        plan = sm.build_plan(data_root=roots.data, app_root=roots.app,
                             current_paths=_paths_stub(), database_path=None)

        assert not any(i.label.startswith("database") for i in plan.items)

    def test_omitting_the_argument_still_autodetects(self, roots, monkeypatch):
        """The default has to keep finding the database actually in use."""
        db = roots.tmp / "live.db"
        db.write_bytes(b"db")
        monkeypatch.setattr(sm, "_current_database_path", lambda: db)

        plan = sm.build_plan(data_root=roots.data, app_root=roots.app,
                             current_paths=_paths_stub())

        assert [i.label for i in plan.items] == ["database"]
        assert plan.items[0].source == db

    def test_a_stub_never_displaces_the_real_gallery(self, roots):
        """
        The configuration can name a nearly-empty directory while the real media
        sits elsewhere. Taking the first populated candidate migrated a stub
        holding one stale file and left a gallery of 23,943 images behind.
        """
        stub = _tree(roots.tmp / "stub-faces", {"face_encodings.json": b"{}"})
        _tree(roots.app, {f"faces/person/{i}.jpg": b"x" for i in range(12)})

        plan = sm.build_plan(data_root=roots.data, app_root=roots.app,
                             current_paths=_paths_stub(faces_dir=stub),
                             database_path=None)

        faces = next(i for i in plan.items if i.label == "faces")
        assert faces.source == roots.app / "faces"
        assert faces.file_count == 12

    def test_data_in_two_places_is_reported_not_silently_dropped(self, roots):
        stub = _tree(roots.tmp / "stub-faces", {"leftover.jpg": b"x"})
        _tree(roots.app, {f"faces/{i}.jpg": b"x" for i in range(5)})

        plan = sm.build_plan(data_root=roots.data, app_root=roots.app,
                             current_paths=_paths_stub(faces_dir=stub),
                             database_path=None)

        assert any("more than one place" in p for p in plan.problems)
        # And preflight refuses, rather than stranding the other copy.
        assert any("more than one place" in p for p in sm.preflight(plan))

    def test_migration_refuses_while_data_is_in_two_places(self, roots):
        stub = _tree(roots.tmp / "stub-faces", {"leftover.jpg": b"x"})
        _tree(roots.app, {f"faces/{i}.jpg": b"x" for i in range(5)})

        plan = sm.build_plan(data_root=roots.data, app_root=roots.app,
                             current_paths=_paths_stub(faces_dir=stub),
                             database_path=None)
        result = sm.migrate(plan)

        assert result["migrated"] is False
        assert (roots.app / "faces" / "0.jpg").exists()
        assert (stub / "leftover.jpg").exists()

    def test_legacy_env_is_picked_up_as_the_config_source(self, roots):
        (roots.app / ".env").write_text("SECRET_KEY=abc\n")

        plan = sm.build_plan(data_root=roots.data, app_root=roots.app,
                             current_paths=_paths_stub(), database_path=None)

        assert plan.config_source == roots.app / ".env"


# ----------------------------------------------------------------- preflight

class TestPreflight:
    def test_refuses_to_merge_into_a_populated_destination(self, roots):
        _tree(roots.app, {"faces/a.jpg": b"x"})
        _tree(roots.data, {"faces/existing.jpg": b"y"})

        plan = sm.build_plan(data_root=roots.data, app_root=roots.app,
                             current_paths=_paths_stub(), database_path=None)
        problems = sm.preflight(plan)

        assert any("already holds data" in p for p in problems)

    def test_a_clean_plan_has_no_problems(self, roots):
        _tree(roots.app, {"faces/a.jpg": b"x"})

        plan = sm.build_plan(data_root=roots.data, app_root=roots.app,
                             current_paths=_paths_stub(), database_path=None)

        assert sm.preflight(plan) == []

    def test_blocked_migration_moves_nothing(self, roots):
        _tree(roots.app, {"faces/a.jpg": b"x"})
        _tree(roots.data, {"faces/existing.jpg": b"y"})

        plan = sm.build_plan(data_root=roots.data, app_root=roots.app,
                             current_paths=_paths_stub(), database_path=None)
        result = sm.migrate(plan)

        assert result["migrated"] is False
        assert (roots.app / "faces" / "a.jpg").exists()      # source untouched
        assert (roots.data / "faces" / "existing.jpg").exists()  # destination untouched


# ----------------------------------------------------------------- migrating

class TestMigrating:
    def test_moves_everything_and_leaves_no_source(self, roots):
        _tree(roots.app, {
            "faces/Mikel/a.jpg": b"aaa",
            "recordings/clip.mp4": b"bbbb",
            "data/snapshots/s.jpg": b"cc",
        })

        plan = sm.build_plan(data_root=roots.data, app_root=roots.app,
                             current_paths=_paths_stub(), database_path=None)
        result = sm.migrate(plan)

        assert result["migrated"] is True
        assert (roots.data / "faces" / "Mikel" / "a.jpg").read_bytes() == b"aaa"
        assert (roots.data / "recordings" / "clip.mp4").read_bytes() == b"bbbb"
        assert (roots.data / "data" / "snapshots" / "s.jpg").read_bytes() == b"cc"
        assert not (roots.app / "faces").exists()
        assert not (roots.app / "recordings").exists()

    def test_dry_run_changes_nothing(self, roots):
        _tree(roots.app, {"faces/a.jpg": b"x"})

        plan = sm.build_plan(data_root=roots.data, app_root=roots.app,
                             current_paths=_paths_stub(), database_path=None)
        result = sm.migrate(plan, dry_run=True)

        assert result["migrated"] is False
        assert (roots.app / "faces" / "a.jpg").exists()
        assert not (roots.data / "faces").exists()

    def test_config_is_copied_and_locked_down(self, roots):
        (roots.app / ".env").write_text("SECRET_KEY=abc\nECOSYSTEM_HMAC_SECRET=z\n")
        _tree(roots.app, {"faces/a.jpg": b"x"})

        plan = sm.build_plan(data_root=roots.data, app_root=roots.app,
                             current_paths=_paths_stub(), database_path=None)
        sm.migrate(plan)

        config = roots.data / "config.env"
        assert "SECRET_KEY=abc" in config.read_text()
        assert oct(config.stat().st_mode)[-3:] == "600"
        # The original is copied, not moved: an unmigrated rollback still works.
        assert (roots.app / ".env").exists()

    def test_stale_storage_settings_are_retired_from_the_config(self, roots):
        """
        Copying the config verbatim would be worse than not copying it: those
        values name directories the migration just emptied, and they take
        precedence over the data root — so the app would come up configured to
        look exactly where its data no longer is.
        """
        (roots.app / ".env").write_text(
            "SECRET_KEY=keep-me\n"
            "OPENEYE_FACES_DIR=/old/faces\n"
            "OPENEYE_SNAPSHOTS_DIR=/old/snaps\n"
            "DATABASE_URL=sqlite:////old/surveillance.db\n"
            "ECOSYSTEM_REGISTRY_URL=http://localhost:8500\n"
        )
        _tree(roots.app, {"faces/a.jpg": b"x"})

        plan = sm.build_plan(data_root=roots.data, app_root=roots.app,
                             current_paths=_paths_stub(), database_path=None)
        sm.migrate(plan)

        text = (roots.data / "config.env").read_text()
        # Secrets and unrelated settings survive untouched.
        assert "SECRET_KEY=keep-me" in text
        assert "ECOSYSTEM_REGISTRY_URL=http://localhost:8500" in text
        # Stale storage settings no longer take effect...
        for key in ("OPENEYE_FACES_DIR", "OPENEYE_SNAPSHOTS_DIR", "DATABASE_URL"):
            assert f"\n{key}=" not in "\n" + text
            # ...but remain visible, so the original intent is not lost.
            assert f"# {key}=" in text

    def test_writes_a_completion_marker(self, roots):
        _tree(roots.app, {"faces/a.jpg": b"x"})

        plan = sm.build_plan(data_root=roots.data, app_root=roots.app,
                             current_paths=_paths_stub(), database_path=None)
        sm.migrate(plan)

        marker = sm.read_marker(roots.data)
        assert marker["status"] == "complete"
        assert marker["version"] == sm.MARKER_VERSION
        assert any(m["label"] == "faces" for m in marker["moved"])

    def test_running_again_is_a_no_op(self, roots):
        _tree(roots.app, {"faces/a.jpg": b"x"})

        first = sm.build_plan(data_root=roots.data, app_root=roots.app,
                              current_paths=_paths_stub(), database_path=None)
        sm.migrate(first)

        second = sm.build_plan(data_root=roots.data, app_root=roots.app,
                               current_paths=_paths_stub(), database_path=None)

        assert second.is_noop
        assert sm.migrate(second)["migrated"] is False

    def test_a_failed_copy_leaves_the_source_alone(self, roots, monkeypatch):
        """The rule that matters most: never delete before verifying."""
        _tree(roots.app, {"faces/a.jpg": b"x"})
        plan = sm.build_plan(data_root=roots.data, app_root=roots.app,
                             current_paths=_paths_stub(), database_path=None)

        item = plan.items[0]
        item.same_filesystem = False       # force the copy-verify-delete path
        item.total_bytes += 999            # make verification disagree

        with pytest.raises(RuntimeError, match="verification failed"):
            sm.migrate(plan)

        assert (roots.app / "faces" / "a.jpg").read_bytes() == b"x"


# ------------------------------------------------------------ the two-way door

class TestExportImport:
    def test_export_copies_without_emptying_the_source(self, roots):
        _tree(roots.data, {"faces/a.jpg": b"x", "recordings/c.mp4": b"y"})
        (roots.data / "surveillance.db").write_bytes(b"db")

        sm.export_data(roots.tmp / "export", data_root=roots.data)

        assert (roots.tmp / "export" / "faces" / "a.jpg").read_bytes() == b"x"
        assert (roots.tmp / "export" / "surveillance.db").read_bytes() == b"db"
        assert (roots.data / "faces" / "a.jpg").exists()

    def test_export_refuses_to_write_inside_itself(self, roots):
        _tree(roots.data, {"faces/a.jpg": b"x"})

        with pytest.raises(ValueError, match="inside the data root"):
            sm.export_data(roots.data / "export", data_root=roots.data)

    def test_round_trip_reproduces_the_tree(self, roots):
        _tree(roots.data, {"faces/Mikel/a.jpg": b"x", "recordings/c.mp4": b"y"})
        (roots.data / "surveillance.db").write_bytes(b"db")

        sm.export_data(roots.tmp / "export", data_root=roots.data)
        restored = roots.tmp / "restored"
        sm.import_data(roots.tmp / "export", data_root=restored)

        assert (restored / "faces" / "Mikel" / "a.jpg").read_bytes() == b"x"
        assert (restored / "recordings" / "c.mp4").read_bytes() == b"y"
        assert (restored / "surveillance.db").read_bytes() == b"db"

    def test_import_refuses_to_overwrite_by_default(self, roots):
        _tree(roots.tmp / "export", {"faces/a.jpg": b"new"})
        _tree(roots.data, {"faces/existing.jpg": b"old"})

        with pytest.raises(ValueError, match="Refusing to import over existing data"):
            sm.import_data(roots.tmp / "export", data_root=roots.data)

        assert (roots.data / "faces" / "existing.jpg").read_bytes() == b"old"

    def test_import_overwrites_when_asked(self, roots):
        _tree(roots.tmp / "export", {"faces/a.jpg": b"new"})
        _tree(roots.data, {"faces/existing.jpg": b"old"})

        sm.import_data(roots.tmp / "export", data_root=roots.data, overwrite=True)

        assert (roots.data / "faces" / "a.jpg").read_bytes() == b"new"

    def test_import_of_a_missing_directory_is_an_error(self, roots):
        with pytest.raises(ValueError, match="No such export directory"):
            sm.import_data(roots.tmp / "nothing", data_root=roots.data)

    def test_exported_config_is_locked_down(self, roots):
        (roots.data).mkdir(parents=True, exist_ok=True)
        (roots.data / "config.env").write_text("SECRET_KEY=abc\n")
        os.chmod(roots.data / "config.env", 0o644)

        sm.export_data(roots.tmp / "export", data_root=roots.data)

        assert oct((roots.tmp / "export" / "config.env").stat().st_mode)[-3:] == "600"
