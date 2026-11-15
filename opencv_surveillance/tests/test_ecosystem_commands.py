"""OpenEye takes snapshots and records clips on hub command (WP1b Task 4).

Cameras, the clip lookup and the hub are fakes: no capture device is opened and
nothing leaves the process.
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

import numpy as np
import pytest

from ecosystem_client.contracts import build_command_envelope, validate_against_schema
from ecosystem_hub import CommandContext, CommandFailed, CommandReceiver
from ecosystem_policy import PolicyEngine

from backend.core import ecosystem_commands as ec

SECRET = "openeye-command-test-secret-0123456789abcdef"
ACTOR = {"id": "x", "type": "service", "app": "ai_for_survival", "device_id": "local-device"}
FIXED_NOW = datetime(2026, 11, 14, 12, 0, 0, tzinfo=timezone.utc)


def run(coro):
    return asyncio.run(coro)


class FakeCamera:
    def __init__(self, frame=None, age=0.1):
        self.frame, self.age = frame, age
        self.recording_requests: list[int] = []
        self.waited: list[tuple] = []

    def get_published_frame(self, since_seq=None, timeout=0.0):
        if since_seq is not None:
            self.waited.append((since_seq, timeout))
        return None if self.frame is None else (self.frame, False, 3)

    def seconds_since_last_frame(self):
        return None if self.frame is None else self.age

    def request_recording(self, duration_seconds):
        self.recording_requests.append(duration_seconds)


class FakeManager:
    def __init__(self, cameras):
        self.cameras = cameras

    def get_camera(self, camera_id):
        return self.cameras.get(camera_id)


class FakeReporter:
    def __init__(self):
        self.reports: list[tuple] = []

    async def __call__(self, command_id, status, *, result=None, error=None):
        self.reports.append((command_id, status, result, error))
        return True


async def _no_sleep(seconds):
    await asyncio.sleep(0)


def _frame():
    return np.zeros((48, 64, 3), dtype=np.uint8)


def _handlers(tmp_path, cameras, *, reporter=None, find_clip=None, **kw):
    return ec.OpenEyeCommandHandlers(
        FakeManager(cameras),
        snapshots_dir=tmp_path / "cmd-snaps",
        reporter=reporter or FakeReporter(),
        find_clip=find_clip or (lambda camera_id, since: None),
        now=lambda: FIXED_NOW,
        sleep=_no_sleep,
        **kw,
    )


def _ctx(command, parameters):
    return CommandContext(
        command_id="01HCMD0000000000000000000C", command=command, action_class="observe",
        actor=dict(ACTOR), target={"scope": "local"}, parameters=parameters, rationale=None,
        correlation_id="corr-1", authorization_ref=None,
    )


# ---- camera.snapshot ---------------------------------------------------------------


def test_snapshot_saves_jpeg_and_returns_reference(tmp_path):
    result = run(_handlers(tmp_path, {"front": FakeCamera(_frame())}).snapshot(
        _ctx("camera.snapshot", {"camera_id": "front"})))
    assert result == {"snapshot_id": "cmd_front_01HCMD0000000000000000000C", "camera_id": "front",
                      "captured_at": "2026-11-14T12:00:00+00:00"}
    saved = tmp_path / "cmd-snaps" / "cmd_front_01HCMD0000000000000000000C.jpg"
    assert saved.read_bytes()[:2] == b"\xff\xd8"  # a JPEG
    assert not any(isinstance(v, (bytes, bytearray)) for v in result.values())


def test_snapshot_unknown_camera_is_failed(tmp_path):
    with pytest.raises(CommandFailed) as err:
        run(_handlers(tmp_path, {}).snapshot(_ctx("camera.snapshot", {"camera_id": "nope"})))
    assert "does not exist" in err.value.message


def test_snapshot_camera_without_frames_fails_fast(tmp_path):
    camera = FakeCamera(frame=None)
    started = time.monotonic()
    with pytest.raises(CommandFailed) as err:
        run(_handlers(tmp_path, {"front": camera}, frame_wait=0.2).snapshot(
            _ctx("camera.snapshot", {"camera_id": "front"})))
    assert "is not producing frames" in err.value.message
    assert time.monotonic() - started < 2
    assert camera.waited == [(0, 0.2)]  # it waited for a frame, bounded by frame_wait


def test_snapshot_stale_frame_waits_for_a_new_one(tmp_path):
    camera = FakeCamera(_frame(), age=60)
    run(_handlers(tmp_path, {"front": camera}).snapshot(_ctx("camera.snapshot", {"camera_id": "front"})))
    assert camera.waited == [(3, ec.FRAME_WAIT_SECONDS)]


@pytest.mark.parametrize("camera_id", ["../etc", "a/b", "", "x" * 129, 7])
def test_snapshot_rejects_a_bad_camera_id(tmp_path, camera_id):
    with pytest.raises(CommandFailed):
        run(_handlers(tmp_path, {"front": FakeCamera(_frame())}).snapshot(
            _ctx("camera.snapshot", {"camera_id": camera_id})))
    assert not (tmp_path / "cmd-snaps").exists()


# ---- camera.record_clip ------------------------------------------------------------


def test_record_clip_returns_accepted_then_reports_result(tmp_path):
    from ecosystem_hub.command_receiver import Accepted

    camera, reporter = FakeCamera(_frame()), FakeReporter()
    lookups: list[tuple] = []

    def find_clip(camera_id, since):
        lookups.append((camera_id, since))
        if len(lookups) < 2:
            return None  # not written yet on the first look
        return {"clip_id": 42, "started_at": "2026-11-14T11:59:58+00:00", "duration_seconds": 10.5}

    handlers = _handlers(tmp_path, {"front": camera}, reporter=reporter, find_clip=find_clip, clip_poll=0)

    async def go():
        outcome = await handlers.record_clip(_ctx("camera.record_clip", {"camera_id": "front", "duration_seconds": 10}))
        assert isinstance(outcome, Accepted) and outcome.job_ref == "clip:01HCMD0000000000000000000C"
        assert reporter.reports == []  # nothing reported before the clip exists
        await asyncio.gather(*handlers._jobs)

    run(go())
    assert camera.recording_requests == [10]
    assert lookups[0] == ("front", FIXED_NOW)
    assert reporter.reports == [("01HCMD0000000000000000000C", "completed",
                                 {"clip_id": 42, "camera_id": "front", "started_at": "2026-11-14T11:59:58+00:00",
                                  "duration_seconds": 10.5}, None)]


def test_record_clip_failure_reports_failed(tmp_path):
    reporter = FakeReporter()
    handlers = _handlers(tmp_path, {"front": FakeCamera(_frame())}, reporter=reporter, clip_deadline_extra=0)

    async def go():
        await handlers.record_clip(_ctx("camera.record_clip", {"camera_id": "front", "duration_seconds": 5}))
        await asyncio.gather(*handlers._jobs)

    run(go())
    [(command_id, status, result, error)] = reporter.reports
    assert status == "failed" and result is None and "no clip was recorded" in error


def test_record_clip_on_a_camera_without_frames_is_failed_now(tmp_path):
    camera = FakeCamera(frame=None)
    with pytest.raises(CommandFailed):
        run(_handlers(tmp_path, {"front": camera}, frame_wait=0.05).record_clip(
            _ctx("camera.record_clip", {"camera_id": "front", "duration_seconds": 10})))
    assert camera.recording_requests == []


@pytest.mark.parametrize("duration", [4, 121, "10", 10.5, True])
def test_duration_outside_bounds_is_rejected_by_schema(tmp_path, duration):
    """The manifest schema states the bounds; the handler enforces all of them.

    The hub's validator applies `minimum` and `type` but not `maximum`, so the
    handler is what stops 121 (and a bool, which JSON-schema validators often
    take for an integer).
    """
    params = {"camera_id": "front", "duration_seconds": duration}
    if duration in (4, "10", 10.5):
        assert validate_against_schema(params, ec.RECORD_CLIP_SCHEMA), duration
    camera = FakeCamera(_frame())
    with pytest.raises(CommandFailed):
        run(_handlers(tmp_path, {"front": camera}).record_clip(_ctx("camera.record_clip", params)))
    assert camera.recording_requests == []


def test_schemas_refuse_unknown_parameters():
    assert validate_against_schema({"camera_id": "front", "extra": 1}, ec.SNAPSHOT_SCHEMA)
    assert not validate_against_schema({"camera_id": "front", "duration_seconds": 30}, ec.RECORD_CLIP_SCHEMA)


# ---- result reporting ----------------------------------------------------------------


def test_result_reporter_signs_the_report_and_stops_on_a_final_refusal():
    import httpx

    seen = []

    def respond(request):
        seen.append(request)
        return httpx.Response(409 if len(seen) > 1 else 200)

    reporter = ec.HubResultReporter("http://hub.test:8500", SECRET, retry_delay=0,
                                    client_factory=lambda: httpx.AsyncClient(transport=httpx.MockTransport(respond)))
    assert run(reporter("01HCMD", "completed", result={"clip_id": 1})) is True
    assert str(seen[0].url) == "http://hub.test:8500/commands/01HCMD/result"
    assert "X-Ecosystem-Signature" in seen[0].headers
    assert run(reporter("01HCMD", "completed")) is False
    assert len(seen) == 2  # a 409 is final: no retry


# ---- manifest and wiring -------------------------------------------------------------


def test_registered_classes_match_the_manifest(tmp_path):
    from backend.core.ecosystem_hub_bridge import build_openeye_capabilities

    receiver = CommandReceiver("openeye", secret=SECRET, policy_engine=PolicyEngine(),
                               replay_db_path=tmp_path / "r.db")
    _handlers(tmp_path, {}).register(receiver)
    manifest = {c["capability"]: c for c in build_openeye_capabilities()}
    for command in receiver.commands:
        assert manifest[command]["action_class"] == receiver._handlers[command][0]
        assert manifest[command]["inputs_schema"]["additionalProperties"] is False


def test_build_receiver_refuses_the_dev_default_secret(tmp_path):
    from ecosystem_auth.tokens import DEFAULT_DEV_SECRET

    assert ec.build_receiver(FakeManager({}), secret=DEFAULT_DEV_SECRET, policy_engine=PolicyEngine(),
                             replay_db_path=tmp_path / "r.db") is None


def test_no_secret_mounts_no_route():
    from fastapi.testclient import TestClient

    from backend.main import app

    previous = getattr(app.state, "command_receiver", None)
    app.state.command_receiver = None
    try:
        resp = TestClient(app).post("/ecosystem/commands", json={})
        assert resp.status_code == 404
    finally:
        app.state.command_receiver = previous


def test_route_round_trip_through_fastapi(tmp_path):
    from fastapi.testclient import TestClient

    from backend.main import app

    receiver = ec.build_receiver(
        FakeManager({"front": FakeCamera(_frame())}), secret=SECRET, policy_engine=PolicyEngine(),
        replay_db_path=tmp_path / "r.db", snapshots_dir=tmp_path / "snaps", reporter=FakeReporter(),
    )
    previous = getattr(app.state, "command_receiver", None)
    app.state.command_receiver = receiver
    try:
        client = TestClient(app)
        env = build_command_envelope("camera.snapshot", "observe", ACTOR, {"scope": "local"}, SECRET,
                                     parameters={"camera_id": "front"}, idempotency_key="rt-1")
        resp = client.post("/ecosystem/commands", json=env)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "completed", body
        assert body["result"]["camera_id"] == "front"
        assert (tmp_path / "snaps" / f"{body['result']['snapshot_id']}.jpg").is_file()

        unsigned = dict(env, idempotency_key="rt-2")
        del unsigned["signature"]
        assert client.post("/ecosystem/commands", json=unsigned).status_code == 401
    finally:
        app.state.command_receiver = previous
