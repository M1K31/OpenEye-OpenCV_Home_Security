# Copyright (c) 2025 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security
"""
Run video capture in a child process, so a native crash cannot kill the server.

Why this exists
---------------
OpenEye died twice on 2026-08-19/20 with SIGSEGV inside OpenCV's AVFoundation
backend: the capture device went away, and a later ``read()`` messaged a freed
Objective-C object. The in-process fixes that followed — one owning thread, a
dead-capture flag, published frames for request handlers — closed every path we
could find. They cannot close the next one, because the fault is in C code whose
state Python cannot inspect, and a segfault is not an exception anyone can catch.

Moving capture into a child process changes the failure from "the security
system is gone" to "a worker died and was restarted". The parent notices, logs
it, and starts a new child.

It also fixes a second, separate defect for free. OpenCV's AVFoundation backend
enumerates capture devices when the process starts, so a camera plugged in after
launch stays invisible for the life of that process — reconnect could never work,
however many times it was retried. A fresh child process performs a fresh
enumeration, so a restarted worker sees devices that appeared after the server
booted.

Design
------
Frames move through ``multiprocessing.shared_memory`` rather than a pipe. A
1080p BGR frame is about 6 MB; at 10 fps a pipe would copy 60 MB/s and serialise
every frame. Shared memory writes once and the parent reads in place.

Two slots are used alternately so the parent never reads the buffer the child is
mid-write on: the child fills the slot the parent is not looking at, then
publishes the new index. A single lock guards only the small metadata block, not
the frame copy, so the reader never blocks the writer for long.

The parent treats the child as untrusted for liveness: it does not ask "did you
crash", it checks whether frames are still arriving. A wedged child that never
segfaults but stops delivering is the same problem as a dead one, and the 22:49
crash proved a capture can report healthy while delivering nothing.
"""

from __future__ import annotations

import ctypes
import logging
import multiprocessing as mp
import os
import time
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Slots in the ring. Two is enough for one writer and one reader: the child
# always writes to the slot the parent is not reading.
SLOT_COUNT = 2

# Upper bound on a single frame. 4K BGR is 3840*2160*3 = ~24.9 MB; this leaves
# room without reserving absurd amounts for the common 1080p case.
MAX_FRAME_BYTES = 4096 * 2304 * 3

# Status values the child publishes for the parent to read.
STATUS_STARTING = 0
STATUS_RUNNING = 1
STATUS_OPEN_FAILED = 2
STATUS_READ_FAILED = 3
STATUS_STOPPED = 4

STATUS_NAMES = {
    STATUS_STARTING: "starting",
    STATUS_RUNNING: "running",
    STATUS_OPEN_FAILED: "open failed",
    STATUS_READ_FAILED: "read failed",
    STATUS_STOPPED: "stopped",
}


@dataclass
class FrameMeta:
    """What the parent needs to interpret the bytes in a slot."""
    seq: int
    slot: int
    height: int
    width: int
    channels: int
    timestamp: float
    status: int

    @property
    def status_name(self) -> str:
        return STATUS_NAMES.get(self.status, f"unknown({self.status})")


# Test seam. Set to "module:callable" and the worker calls that instead of
# opening a real device. An environment variable rather than a monkeypatch
# because the child is started with 'spawn', which re-imports this module in a
# fresh interpreter — patched attributes in the parent do not reach it. Spawn is
# deliberate: a fresh interpreter is precisely what makes AVFoundation
# re-enumerate devices, which is how a restarted worker sees a camera that was
# plugged in after the server booted.
CAPTURE_FACTORY_ENV = "OPENEYE_CAPTURE_FACTORY"


def _open_capture(source: str):
    """Open a capture for a device index or a stream URL."""
    override = os.getenv(CAPTURE_FACTORY_ENV)
    if override:
        module_name, _, attr = override.partition(":")
        import importlib
        factory = getattr(importlib.import_module(module_name), attr)
        return factory(source)

    # Imported here so the parent process never imports cv2 on this module's
    # account, and so the child imports it fresh.
    import cv2

    try:
        device_index = int(source)
        return cv2.VideoCapture(device_index)
    except (ValueError, TypeError):
        return cv2.VideoCapture(source, cv2.CAP_FFMPEG)


def _capture_worker(source: str, shm_name: str, meta_array, stop_event, target_fps: float):
    """
    Child-process entry point. Owns the capture device for its whole lifetime.

    Never raises into the parent: the parent's contract is "frames arrive or they
    do not", and a child that dies is restarted. Anything unexpected is recorded
    in the status field and the process exits so the parent can start a clean one.
    """
    from multiprocessing.shared_memory import SharedMemory

    shm = None
    capture = None
    try:
        shm = SharedMemory(name=shm_name)
        buffer = np.ndarray((SLOT_COUNT, MAX_FRAME_BYTES), dtype=np.uint8, buffer=shm.buf)

        capture = _open_capture(source)
        if capture is None or not capture.isOpened():
            with meta_array.get_lock():
                meta_array[6] = STATUS_OPEN_FAILED
            return

        try:
            if target_fps:
                capture.set(__import__("cv2").CAP_PROP_FPS, float(target_fps))
        except Exception:
            pass  # Many devices ignore this; never fatal.

        with meta_array.get_lock():
            meta_array[6] = STATUS_RUNNING

        seq = 0
        interval = 1.0 / target_fps if target_fps else 0.0
        consecutive_failures = 0

        while not stop_event.is_set():
            started = time.time()
            ok, frame = capture.read()

            if not ok or frame is None:
                consecutive_failures += 1
                # Give up quickly rather than retrying into a device that may
                # already be gone. Dying here is CHEAP — the parent starts a new
                # child, which also re-enumerates devices. That is the whole
                # advantage of being a subprocess.
                if consecutive_failures >= 3:
                    with meta_array.get_lock():
                        meta_array[6] = STATUS_READ_FAILED
                    return
                time.sleep(0.1)
                continue

            consecutive_failures = 0

            nbytes = frame.nbytes
            if nbytes > MAX_FRAME_BYTES:
                # Refusing is better than a partial write the parent would
                # happily reinterpret as a valid frame.
                with meta_array.get_lock():
                    meta_array[6] = STATUS_READ_FAILED
                return

            slot = seq % SLOT_COUNT   # the slot the parent is not reading
            buffer[slot, :nbytes] = frame.reshape(-1)

            seq += 1
            h, w = frame.shape[0], frame.shape[1]
            c = frame.shape[2] if frame.ndim == 3 else 1
            with meta_array.get_lock():
                meta_array[0] = seq
                meta_array[1] = slot
                meta_array[2] = h
                meta_array[3] = w
                meta_array[4] = c
                meta_array[5] = time.time()
                meta_array[6] = STATUS_RUNNING

            if interval:
                elapsed = time.time() - started
                if elapsed < interval:
                    time.sleep(interval - elapsed)
    except Exception:
        # The parent cannot see this traceback, so record a status it can read.
        try:
            with meta_array.get_lock():
                meta_array[6] = STATUS_READ_FAILED
        except Exception:
            pass
    finally:
        if capture is not None:
            try:
                capture.release()
            except Exception:
                pass
        if shm is not None:
            try:
                shm.close()
            except Exception:
                pass


class CaptureClient:
    """
    Parent-side handle on a capture running in a child process.

    Reading a frame here can never segfault the server: this process holds no
    capture object and calls no OpenCV capture function.
    """

    # A child that has not published a frame for this long is considered wedged
    # and is replaced. Deliberately generous compared with the in-process
    # dead-capture threshold, because restarting a process costs more than
    # releasing a handle.
    STALL_TIMEOUT = float(os.getenv("OPENEYE_CAPTURE_STALL_TIMEOUT", "10"))

    # Floor between restart attempts, doubling up to the ceiling, so an absent
    # device costs one spawn a minute rather than a spawn loop.
    RESTART_BACKOFF_MIN = 1.0
    RESTART_BACKOFF_MAX = float(os.getenv("OPENEYE_CAPTURE_RESTART_MAX", "60"))

    def __init__(self, source: str, camera_id: str, target_fps: float = 15.0):
        self.source = source
        self.camera_id = camera_id
        self.target_fps = target_fps

        self._shm = None
        self._buffer = None
        self._meta = None
        self._process: Optional[mp.Process] = None
        self._stop_event = None

        self._last_seq = 0
        self._restart_count = 0
        self._next_restart_allowed = 0.0
        self._backoff = self.RESTART_BACKOFF_MIN

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> bool:
        """Allocate shared memory and spawn the worker. True if it spawned."""
        from multiprocessing.shared_memory import SharedMemory

        try:
            self._shm = SharedMemory(create=True, size=SLOT_COUNT * MAX_FRAME_BYTES)
            self._buffer = np.ndarray(
                (SLOT_COUNT, MAX_FRAME_BYTES), dtype=np.uint8, buffer=self._shm.buf
            )
            # seq, slot, h, w, c, timestamp, status
            self._meta = mp.Array(ctypes.c_double, 7)
            self._stop_event = mp.Event()

            self._process = mp.Process(
                target=_capture_worker,
                args=(self.source, self._shm.name, self._meta, self._stop_event, self.target_fps),
                daemon=True,
                name=f"capture_{self.camera_id}",
            )
            self._process.start()
            logger.info(
                "Camera %s: capture worker started (pid %s, source %s)",
                self.camera_id, self._process.pid, self.source)
            return True
        except Exception as e:
            logger.error("Camera %s: could not start capture worker: %s", self.camera_id, e)
            self.stop()
            return False

    def stop(self) -> None:
        """Stop the worker and release shared memory."""
        if self._stop_event is not None:
            try:
                self._stop_event.set()
            except Exception:
                pass

        if self._process is not None and self._process.is_alive():
            self._process.join(timeout=3.0)
            if self._process.is_alive():
                logger.warning("Camera %s: capture worker did not exit, terminating",
                               self.camera_id)
                self._process.terminate()
                self._process.join(timeout=2.0)
        self._process = None

        if self._shm is not None:
            try:
                self._shm.close()
                self._shm.unlink()
            except FileNotFoundError:
                pass
            except Exception as e:
                logger.debug("Camera %s: releasing shared memory raised %s", self.camera_id, e)
        self._shm = None
        self._buffer = None

    # -- reading -----------------------------------------------------------

    def _read_meta(self) -> Optional[FrameMeta]:
        if self._meta is None:
            return None
        with self._meta.get_lock():
            return FrameMeta(
                seq=int(self._meta[0]), slot=int(self._meta[1]),
                height=int(self._meta[2]), width=int(self._meta[3]),
                channels=int(self._meta[4]), timestamp=float(self._meta[5]),
                status=int(self._meta[6]),
            )

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Return (True, frame) for a frame newer than the last one returned.

        Mirrors cv2.VideoCapture.read()'s shape so calling code reads the same,
        but nothing here can crash the process.
        """
        meta = self._read_meta()
        if meta is None or meta.seq == 0 or meta.seq == self._last_seq:
            return False, None
        if meta.height <= 0 or meta.width <= 0:
            return False, None

        nbytes = meta.height * meta.width * meta.channels
        if nbytes > MAX_FRAME_BYTES:
            return False, None

        # Copy out: the child may reuse this slot two frames from now, and
        # callers hold frames well beyond that (recording, face recognition).
        flat = self._buffer[meta.slot, :nbytes]
        frame = np.array(flat, dtype=np.uint8).reshape(meta.height, meta.width, meta.channels)

        self._last_seq = meta.seq
        return True, frame

    # -- health ------------------------------------------------------------

    def is_alive(self) -> bool:
        return self._process is not None and self._process.is_alive()

    def seconds_since_frame(self) -> Optional[float]:
        meta = self._read_meta()
        if meta is None or meta.timestamp <= 0:
            return None
        return time.time() - meta.timestamp

    def status(self) -> str:
        meta = self._read_meta()
        return meta.status_name if meta else "not started"

    def needs_restart(self) -> bool:
        """
        True when the worker is dead or has stopped producing.

        Liveness is judged on frames arriving, not on the process existing: the
        22:49 crash showed a capture can look healthy and deliver nothing for
        fourteen hours.
        """
        if not self.is_alive():
            return True
        age = self.seconds_since_frame()
        if age is None:
            # Never produced. Give it the stall window from spawn to open the
            # device, which on macOS can include a permission prompt.
            return False
        return age > self.STALL_TIMEOUT

    def restart_if_needed(self) -> bool:
        """
        Replace a dead or wedged worker, honouring backoff. True if restarted.

        A restart is also the fix for a camera attached after the server booted:
        the new child enumerates devices afresh.
        """
        if not self.needs_restart():
            self._backoff = self.RESTART_BACKOFF_MIN
            return False

        now = time.time()
        if now < self._next_restart_allowed:
            return False

        exit_code = self._process.exitcode if self._process is not None else None
        if exit_code is not None and exit_code < 0:
            # Negative exit code means killed by a signal. -11 is SIGSEGV: the
            # crash that used to take the whole application down, now confined
            # to a worker we can simply replace.
            logger.error(
                "Camera %s: capture worker died with signal %s%s. Restarting.",
                self.camera_id, -exit_code,
                " (SIGSEGV — the native capture crash, contained)" if exit_code == -11 else "")
        else:
            logger.warning(
                "Camera %s: capture worker unhealthy (status=%s, alive=%s). Restarting.",
                self.camera_id, self.status(), self.is_alive())

        self.stop()
        self._restart_count += 1
        self._last_seq = 0
        started = self.start()

        self._next_restart_allowed = time.time() + self._backoff
        self._backoff = min(self._backoff * 2, self.RESTART_BACKOFF_MAX)
        return started

    @property
    def restart_count(self) -> int:
        return self._restart_count

    # -- cv2.VideoCapture-shaped surface -----------------------------------
    #
    # These let a CaptureClient stand in for a cv2.VideoCapture object, so
    # camera_manager keeps its existing shape — dead-capture handling, frame
    # publishing and failure counting all work unchanged. The difference is that
    # every call here is pure Python over shared memory, so none of it can
    # segfault the server.

    def isOpened(self) -> bool:
        """True while the worker is running and has not been declared stalled."""
        return self.is_alive() and not self.needs_restart()

    def release(self) -> None:
        """Match VideoCapture.release(); stops the worker and frees memory."""
        self.stop()

    def set(self, *_args) -> bool:
        # Frame rate is fixed when the worker is spawned; nothing to set here.
        return False

    def get(self, *_args) -> float:
        return 0.0
