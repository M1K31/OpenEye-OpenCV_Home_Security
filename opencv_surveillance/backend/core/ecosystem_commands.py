"""OpenEye's side of hub command dispatch: snapshots and clips (WP1b Task 4).

The hub forwards a command to `POST /ecosystem/commands`; the CommandReceiver
from appecosystem-hub verifies it, runs OpenEye's own policy gate, then calls a
handler here. Results are references, never image or video bytes: viewing a
snapshot or a clip stays behind OpenEye's own authentication.

- `camera.snapshot` stores one JPEG from the camera's latest processed frame in
  the snapshot directory and returns `{snapshot_id, camera_id, captured_at}`.
  A camera with no frame within a few seconds fails fast instead of hanging.
- `camera.record_clip` opens the camera's existing manual-recording window and
  returns `accepted`. When the clip has been written, its id is reported to the
  hub with `POST /commands/{id}/result` (signed with the ecosystem secret), or
  `failed` if no clip appeared.

Frames are read with `get_published_frame`, which never touches the capture
device, so a command cannot disturb the camera's own processing loop.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

APP_NAME = "openeye"
FRAME_WAIT_SECONDS = 5.0
CLIP_MIN_SECONDS, CLIP_MAX_SECONDS = 5, 120
# A requested window can extend a motion recording already in progress; the
# recorder caps a clip at 300 s, so the result is awaited at most that long more.
CLIP_REPORT_DEADLINE_EXTRA = 330.0

_CAMERA_ID = {"type": "string", "minLength": 1, "maxLength": 128, "pattern": "^[A-Za-z0-9_.:-]+$"}
SNAPSHOT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"camera_id": _CAMERA_ID},
    "required": ["camera_id"],
    "additionalProperties": False,
}
RECORD_CLIP_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "camera_id": _CAMERA_ID,
        "duration_seconds": {"type": "integer", "minimum": CLIP_MIN_SECONDS, "maximum": CLIP_MAX_SECONDS},
    },
    "required": ["camera_id", "duration_seconds"],
    "additionalProperties": False,
}


def _command_failed(message: str) -> Exception:
    from ecosystem_hub import CommandFailed

    return CommandFailed(message)


def _utc_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


class HubResultReporter:
    """Reports an accepted command's outcome to the hub (`POST /commands/{id}/result`), signed."""

    def __init__(
        self,
        registry_url: str,
        secret: str,
        *,
        client_factory: Callable[[], Any] | None = None,
        timeout: float = 5.0,
        attempts: int = 3,
        retry_delay: float = 2.0,
    ):
        import httpx

        self.registry_url = registry_url.rstrip("/")
        self._secret = secret
        self._client_factory = client_factory or (lambda: httpx.AsyncClient(timeout=timeout))
        self._attempts = max(1, attempts)
        self._retry_delay = retry_delay

    async def __call__(self, command_id: str, status: str, *, result: dict | None = None,
                       error: str | None = None) -> bool:
        import json

        from ecosystem_auth.tokens import sign_request

        url = f"{self.registry_url}/commands/{command_id}/result"
        body = {"status": status, "result": result, "error": error}
        for attempt in range(self._attempts):
            try:
                headers = sign_request("POST", url, self._secret, body=body)
                headers["Content-Type"] = "application/json"
                async with self._client_factory() as client:
                    resp = await client.post(url, content=json.dumps(body), headers=headers)
                if resp.status_code == 200:
                    return True
                if resp.status_code in (403, 404, 409, 422):
                    # The hub refused this report for good; repeating it changes nothing.
                    logger.warning("Hub refused the result of %s: HTTP %s", command_id, resp.status_code)
                    return False
            except Exception as exc:
                logger.warning("Could not report the result of %s (attempt %d): %r", command_id, attempt + 1, exc)
            if attempt + 1 < self._attempts:
                await asyncio.sleep(self._retry_delay * (attempt + 1))
        return False


# Slack at each end of a window: the processing loop starts and stops a clip on
# the next frame, and timestamps are taken in different places.
WINDOW_SLACK_SECONDS = 3.0
# Clips the recorder split (it caps one at 300 s) still count as contiguous.
CLIP_GAP_SECONDS = 2.0


def clips_covering(clips: list[dict[str, Any]], start: datetime, end: datetime) -> dict[str, Any] | None:
    """Whether `clips` (each {id, started_at, ended_at, duration_seconds}) cover [start, end].

    Returns None when no clip overlaps the window; otherwise
    {clip_id, clip_ids, started_at, duration_seconds, covers_window}, where
    covers_window means contiguous clips run from the window's start to its end.
    """
    slack, gap = timedelta(seconds=WINDOW_SLACK_SECONDS), timedelta(seconds=CLIP_GAP_SECONDS)
    overlapping = sorted(
        (c for c in clips if c.get("ended_at") and c.get("started_at")
         and c["ended_at"] >= start and c["started_at"] <= end),
        key=lambda c: c["started_at"],
    )
    if not overlapping:
        return None
    covered_until = None
    covers = overlapping[0]["started_at"] <= start + slack
    for clip in overlapping:
        if covered_until is not None and clip["started_at"] > covered_until + gap:
            covers = False
        covered_until = max(covered_until or clip["ended_at"], clip["ended_at"])
    covers = covers and covered_until >= end - slack
    return {
        "clip_id": overlapping[0]["id"],
        "clip_ids": [c["id"] for c in overlapping],
        "started_at": _utc_iso(overlapping[0]["started_at"]),
        "duration_seconds": sum(float(c.get("duration_seconds") or 0) for c in overlapping),
        "covers_window": bool(covers),
    }


def find_recorded_clip(camera_id: str, start: datetime, end: datetime) -> dict[str, Any] | None:
    """The clips recorded on `camera_id` for the window [start, end]; see `clips_covering`."""
    from backend.database import models
    from backend.database.utils import get_db_context

    def naive(dt: datetime) -> datetime:
        return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt

    with get_db_context() as db:
        rows = (
            db.query(models.RecordingEvent)
            .filter(models.RecordingEvent.camera_id == camera_id)
            .filter(models.RecordingEvent.ended_at.isnot(None))
            .filter(models.RecordingEvent.ended_at >= naive(start))
            .filter(models.RecordingEvent.started_at <= naive(end))
            .all()
        )
        clips = [
            {"id": r.id, "started_at": r.started_at.replace(tzinfo=timezone.utc),
             "ended_at": r.ended_at.replace(tzinfo=timezone.utc), "duration_seconds": r.duration_seconds}
            for r in rows
        ]
    return clips_covering(clips, start, end)


FindClip = Callable[[str, datetime, datetime], "dict[str, Any] | None"]
Reporter = Callable[..., Awaitable[bool]]


class OpenEyeCommandHandlers:
    def __init__(
        self,
        camera_manager: Any,
        *,
        snapshots_dir: Path | Callable[[], Path],
        reporter: Reporter,
        find_clip: FindClip = find_recorded_clip,
        frame_wait: float = FRAME_WAIT_SECONDS,
        clip_grace: float = 10.0,
        clip_poll: float = 5.0,
        clip_deadline_extra: float = CLIP_REPORT_DEADLINE_EXTRA,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self._cameras = camera_manager
        self._snapshots_dir = snapshots_dir
        self._report = reporter
        self._find_clip = find_clip
        self._frame_wait = frame_wait
        self._clip_grace = clip_grace
        self._clip_poll = clip_poll
        self._clip_deadline_extra = clip_deadline_extra
        self._now = now
        self._sleep = sleep
        self._jobs: set[asyncio.Task] = set()

    # ---- shared --------------------------------------------------------------

    def _camera(self, ctx: Any) -> tuple[str, Any]:
        camera_id = (ctx.parameters or {}).get("camera_id")
        if not isinstance(camera_id, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", camera_id):
            raise _command_failed("camera_id must be a camera id")
        camera = self._cameras.get_camera(camera_id)
        if camera is None:
            raise _command_failed(f"camera {camera_id} does not exist")
        return camera_id, camera

    async def _fresh_frame(self, camera_id: str, camera: Any) -> Any:
        """The latest processed frame, waiting at most `frame_wait` for one; CommandFailed if none."""
        if not hasattr(camera, "get_published_frame"):
            raise _command_failed(f"camera {camera_id} is not producing frames")
        published = camera.get_published_frame()
        age = camera.seconds_since_last_frame() if hasattr(camera, "seconds_since_last_frame") else None
        if published is None or age is None or age > self._frame_wait:
            since = published[2] if published else 0
            published = await asyncio.to_thread(camera.get_published_frame, since, self._frame_wait)
        if published is None or published[0] is None:
            raise _command_failed(f"camera {camera_id} is not producing frames")
        return published[0]

    # ---- camera.snapshot -----------------------------------------------------

    async def snapshot(self, ctx: Any) -> dict[str, Any]:
        import cv2

        camera_id, camera = self._camera(ctx)
        frame = await self._fresh_frame(camera_id, camera)
        captured_at = self._now()
        ok, jpeg = cv2.imencode(".jpg", frame)
        if not ok:
            raise _command_failed(f"could not encode a snapshot from camera {camera_id}")

        directory = self._snapshots_dir() if callable(self._snapshots_dir) else self._snapshots_dir
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        safe_camera = re.sub(r"[^A-Za-z0-9_-]", "_", camera_id)
        snapshot_id = f"cmd_{safe_camera}_{ctx.command_id}"
        path = directory / f"{snapshot_id}.jpg"
        await asyncio.to_thread(path.write_bytes, jpeg.tobytes())
        return {"snapshot_id": snapshot_id, "camera_id": camera_id, "captured_at": _utc_iso(captured_at)}

    # ---- camera.record_clip --------------------------------------------------

    async def record_clip(self, ctx: Any) -> Any:
        from ecosystem_hub.command_receiver import Accepted

        duration = (ctx.parameters or {}).get("duration_seconds")
        if not isinstance(duration, int) or isinstance(duration, bool) or not (
            CLIP_MIN_SECONDS <= duration <= CLIP_MAX_SECONDS
        ):
            raise _command_failed(
                f"duration_seconds must be an integer from {CLIP_MIN_SECONDS} to {CLIP_MAX_SECONDS}"
            )
        camera_id, camera = self._camera(ctx)
        # A camera that is not producing frames would record nothing; say so now.
        await self._fresh_frame(camera_id, camera)

        requested_at = self._now()
        camera.request_recording(duration)
        job = asyncio.get_running_loop().create_task(
            self._finish_clip(ctx.command_id, camera_id, requested_at, duration)
        )
        self._jobs.add(job)
        job.add_done_callback(self._jobs.discard)
        return Accepted(f"clip:{ctx.command_id}")

    async def _finish_clip(self, command_id: str, camera_id: str, requested_at: datetime, duration: int) -> None:
        """Wait until clips cover the whole requested window, then report them (or the shortfall)."""
        window_end = requested_at + timedelta(seconds=duration)
        try:
            await self._sleep(duration + self._clip_grace)
            deadline = time.monotonic() + self._clip_deadline_extra
            clip = None
            while True:
                clip = await asyncio.to_thread(self._find_clip, camera_id, requested_at, window_end)
                if (clip is not None and clip.get("covers_window")) or time.monotonic() >= deadline:
                    break
                await self._sleep(self._clip_poll)
            if clip is None:
                await self._report(command_id, "failed", error=f"no clip was recorded on camera {camera_id}")
                return
            result = {
                "clip_id": clip["clip_id"],
                "clip_ids": clip.get("clip_ids", [clip["clip_id"]]),
                "camera_id": camera_id,
                "started_at": clip.get("started_at"),
                "duration_seconds": clip.get("duration_seconds", duration),
            }
            if not clip.get("covers_window"):
                await self._report(
                    command_id, "failed", result=result,
                    error=f"the clips on camera {camera_id} cover only part of the requested {duration}s",
                )
                return
            await self._report(command_id, "completed", result=result)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Clip job for %s failed", command_id)
            try:
                await self._report(command_id, "failed", error=type(exc).__name__)
            except Exception:
                pass

    def register(self, receiver: Any) -> None:
        receiver.register("camera.snapshot", "observe", self.snapshot, timeout_seconds=15)
        receiver.register("camera.record_clip", "observe", self.record_clip, timeout_seconds=15)


def resolve_command_secret(secret: str | None = None) -> str | None:
    """The ecosystem secret, checked by appecosystem-auth (no dev default), or None."""
    from ecosystem_auth.tokens import get_ecosystem_secret

    try:
        return get_ecosystem_secret(secret or None) or None
    except Exception:
        return None


def build_receiver(
    camera_manager: Any,
    *,
    secret: str | None = None,
    registry_url: str | None = None,
    policy_engine: Any = None,
    replay_db_path: str | Path | None = None,
    **handler_options: Any,
) -> Any:
    """A CommandReceiver with OpenEye's handlers, or None when no valid ecosystem secret is set."""
    import os

    from ecosystem_hub.command_adapters import build_receiver_from_env

    resolved = resolve_command_secret(secret)
    if not resolved:
        logger.info("No usable ecosystem secret; OpenEye accepts no hub commands.")
        return None
    from backend.core import ecosystem_hub_bridge as bridge

    if policy_engine is None:
        policy_engine = bridge.get_policy_engine()
    if replay_db_path is None:
        replay_db_path = bridge._policy_state_dir() / "received_commands.db"
    registry_url = registry_url or os.environ.get("ECOSYSTEM_REGISTRY_URL") or "http://localhost:8500"
    receiver = build_receiver_from_env(
        APP_NAME,
        policy_engine=policy_engine,
        replay_db_path=replay_db_path,
        registry_url=registry_url,
        secret=resolved,
    )
    if receiver is None:
        return None
    if "snapshots_dir" not in handler_options:
        from backend.core.paths import paths

        handler_options["snapshots_dir"] = lambda: paths.snapshots_dir
    handler_options.setdefault("reporter", HubResultReporter(registry_url, resolved))
    OpenEyeCommandHandlers(camera_manager, **handler_options).register(receiver)
    return receiver
