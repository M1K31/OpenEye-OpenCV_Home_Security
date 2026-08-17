# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
The shutdown handler must not cancel itself.

`asyncio.all_tasks()` includes the coroutine calling it. Cancelling everything
it returns therefore cancels the shutdown handler mid-shutdown, and awaiting the
result raises CancelledError inside the very coroutine that asked for it.

CancelledError inherits from BaseException, not Exception, so an `except
Exception` around it catches nothing: the error escapes, every quit ends in a
traceback, and any shutdown step after that point is skipped.

These tests exercise the pattern rather than importing the app, because
constructing the whole application to test one loop is slower than the thing
being tested and fails for unrelated reasons.
"""

import asyncio
import time

import pytest


async def _cancel_pending(exclude_self: bool):
    """The shutdown step, with the defect switchable."""
    current = asyncio.current_task()
    tasks = [
        t for t in asyncio.all_tasks()
        if not t.done() and (t is not current or not exclude_self)
    ]
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True), timeout=3.0)
    return len(tasks)


async def _long_runner():
    try:
        await asyncio.sleep(60)
    except asyncio.CancelledError:
        raise


class TestSelfCancellation:
    @pytest.mark.asyncio
    async def test_the_old_shape_cancels_itself(self):
        """Reproduces the reported failure, so the fix has something to prove."""
        victim = asyncio.create_task(_long_runner())
        await asyncio.sleep(0)

        with pytest.raises(asyncio.CancelledError):
            await _cancel_pending(exclude_self=False)

        victim.cancel()

    @pytest.mark.asyncio
    async def test_excluding_the_current_task_shuts_down_cleanly(self):
        victim = asyncio.create_task(_long_runner())
        await asyncio.sleep(0)

        cancelled = await _cancel_pending(exclude_self=True)

        assert cancelled >= 1
        assert victim.cancelled() or victim.done()

    @pytest.mark.asyncio
    async def test_no_pending_tasks_is_not_an_error(self):
        assert await _cancel_pending(exclude_self=True) >= 0

    @pytest.mark.asyncio
    async def test_a_task_that_ignores_cancellation_does_not_hang_shutdown(self):
        """
        A task that swallows CancelledError must cost the timeout, not the
        session. Quitting has to finish either way.

        The uncooperative task has a deadline of its own. The first version of
        this test used `while True`, which made it genuinely immortal — cancel
        could not stop it, so pytest's event-loop teardown waited on it forever
        and the whole run hung. A test for "shutdown must not hang" that hangs
        the suite is worse than no test: it fails in a way that looks like the
        code under test rather than the test.
        """
        async def uncooperative():
            deadline = time.monotonic() + 0.6
            while time.monotonic() < deadline:
                try:
                    await asyncio.sleep(0.05)
                except asyncio.CancelledError:
                    pass  # deliberately ignores the request, but not forever

        task = asyncio.create_task(uncooperative())
        await asyncio.sleep(0)

        current = asyncio.current_task()
        tasks = [t for t in asyncio.all_tasks() if t is not current and not t.done()]
        for t in tasks:
            t.cancel()

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True), timeout=0.15)

        # Reap it, so the loop closes cleanly and the next test starts fresh.
        await asyncio.wait_for(
            asyncio.gather(task, return_exceptions=True), timeout=3.0)
        assert task.done()
