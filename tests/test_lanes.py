import pytest
import asyncio

from orchestration.lanes import LaneQueue, LanePriority


@pytest.mark.asyncio
async def test_lane_register():
    lq = LaneQueue()
    lane = lq.register("main", LanePriority.MAIN)
    assert lane.name == "main"
    assert lq.get_lane("main") is lane


@pytest.mark.asyncio
async def test_lane_priority_order():
    lq = LaneQueue()
    main_lane = lq.register("main", LanePriority.MAIN)
    cron_lane = lq.register("cron", LanePriority.CRON)
    heartbeat_lane = lq.register("heartbeat", LanePriority.HEARTBEAT)

    # Put items in reverse priority order
    await heartbeat_lane.put("heartbeat_msg")
    await cron_lane.put("cron_msg")
    await main_lane.put("main_msg")

    # Consume should drain main first
    lane_name, item = await lq.consume()
    assert lane_name == "main"
    assert item == "main_msg"

    lane_name, item = await lq.consume()
    assert lane_name == "cron"
    assert item == "cron_msg"

    lane_name, item = await lq.consume()
    assert lane_name == "heartbeat"
    assert item == "heartbeat_msg"


@pytest.mark.asyncio
async def test_lane_sizes():
    lq = LaneQueue()
    lq.register("a", LanePriority.MAIN)
    lq.register("b", LanePriority.CRON)

    await lq.get_lane("a").put("x")
    await lq.get_lane("a").put("y")

    sizes = lq.sizes()
    assert sizes == {"a": 2, "b": 0}
