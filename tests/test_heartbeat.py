import pytest
import asyncio

from orchestration.heartbeat import HeartbeatService


@pytest.mark.asyncio
async def test_heartbeat_fires():
    count = 0

    async def on_hb():
        nonlocal count
        count += 1

    svc = HeartbeatService(interval_seconds=0.05, on_heartbeat=on_hb)
    await svc.start()
    assert svc.is_running

    await asyncio.sleep(0.2)
    await svc.stop()

    assert count >= 2
    assert not svc.is_running


@pytest.mark.asyncio
async def test_heartbeat_check_fn_blocks():
    count = 0

    async def check():
        return False  # always skip

    async def on_hb():
        nonlocal count
        count += 1

    svc = HeartbeatService(interval_seconds=0.05, check_fn=check, on_heartbeat=on_hb)
    await svc.start()
    await asyncio.sleep(0.2)
    await svc.stop()

    assert count == 0


@pytest.mark.asyncio
async def test_heartbeat_no_callback():
    svc = HeartbeatService(interval_seconds=0.05)
    await svc.start()
    await asyncio.sleep(0.1)
    await svc.stop()
    # Should not raise
