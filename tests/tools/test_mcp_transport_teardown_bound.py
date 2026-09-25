"""Invariant tests: leaving a remote MCP transport is time-bounded.

After a peer (hub) restart the SDK's writer can block on the dead stream ("transport write
blocked"). An unbounded ``__aexit__`` on the session or stream pump then leaves the server in
``degraded`` until the whole process restarts, because run()'s retry/park loop only runs after
``_serve_transport`` returns. The teardown must give up after ``_TRANSPORT_TEARDOWN_TIMEOUT`` and
hand the lifecycle result back so the reconnect proceeds.
"""

import asyncio
import logging
from contextlib import asynccontextmanager

import anyio
import pytest

from tools import mcp_tool as _core
from tools.mcp_tool import MCPServerTask


@asynccontextmanager
async def _hanging_exit():
    """A context whose exit never finishes on its own — a blocked write on a dead stream."""
    yield (object(), object())
    await anyio.sleep_forever()


@asynccontextmanager
async def _hanging_task_group():
    """Stream pump shape: a TaskGroup whose child blocks forever, so the group's exit waits on it."""
    async with anyio.create_task_group() as tg:
        tg.start_soon(anyio.sleep_forever)
        yield (object(), object())


@asynccontextmanager
async def _clean():
    yield (object(), object())


def _task(monkeypatch, session_cm, lifecycle="reconnect"):
    task = MCPServerTask("t")
    task._config = {"url": "http://127.0.0.1:1/mcp"}

    async def fake_serve_session(self, session, timeout, label):
        return lifecycle

    monkeypatch.setattr(MCPServerTask, "_serve_session", fake_serve_session)
    monkeypatch.setattr(MCPServerTask, "_session_kwargs", lambda self: {})
    monkeypatch.setattr(_core, "ClientSession", lambda *a, **k: session_cm())
    monkeypatch.setattr(_core, "_TRANSPORT_TEARDOWN_TIMEOUT", 0.05)
    return task


async def _serve(task, transport_cm):
    # The outer wait_for is the test's own safety net: without the fix this would hang forever.
    return await asyncio.wait_for(
        task._serve_transport(transport_cm, "HTTP", 1.0), timeout=5
    )


@pytest.mark.parametrize("transport", [_hanging_exit, _hanging_task_group])
def test_hanging_transport_teardown_is_abandoned(monkeypatch, caplog, transport):
    task = _task(monkeypatch, _clean)
    with caplog.at_level(logging.WARNING, logger="tools.mcp_tool"):
        assert asyncio.run(_serve(task, transport())) == "reconnect"
    assert "teardown exceeded" in caplog.text


def test_hanging_session_exit_is_abandoned(monkeypatch, caplog):
    task = _task(monkeypatch, _hanging_exit)
    with caplog.at_level(logging.WARNING, logger="tools.mcp_tool"):
        assert asyncio.run(_serve(task, _clean())) == "reconnect"
    assert "teardown exceeded" in caplog.text


@pytest.mark.parametrize("lifecycle", ["reconnect", "shutdown", "recycle"])
def test_clean_teardown_returns_lifecycle_without_warning(
    monkeypatch, caplog, lifecycle
):
    task = _task(monkeypatch, _clean, lifecycle=lifecycle)
    with caplog.at_level(logging.WARNING, logger="tools.mcp_tool"):
        assert asyncio.run(_serve(task, _clean())) == lifecycle
    assert "teardown exceeded" not in caplog.text


def test_serving_itself_is_not_bounded(monkeypatch):
    """The deadline arms only after serving returns: a long-lived session is never cut short."""
    task = _task(monkeypatch, _clean)

    async def slow_serve_session(self, session, timeout, label):
        await anyio.sleep(0.2)  # 4x the teardown ceiling
        return "shutdown"

    monkeypatch.setattr(MCPServerTask, "_serve_session", slow_serve_session)
    assert asyncio.run(_serve(task, _clean())) == "shutdown"
