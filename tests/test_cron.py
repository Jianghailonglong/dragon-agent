import pytest
import asyncio

from orchestration.cron import CronScheduler


@pytest.mark.asyncio
async def test_cron_runs_job():
    count = 0

    async def job_fn():
        nonlocal count
        count += 1

    scheduler = CronScheduler()
    scheduler.add_job("test", interval_seconds=0.1, callback=job_fn)
    await scheduler.start()

    await asyncio.sleep(1.5)
    await scheduler.stop()

    assert count >= 3


@pytest.mark.asyncio
async def test_cron_manual_trigger():
    count = 0

    async def job_fn():
        nonlocal count
        count += 1

    scheduler = CronScheduler()
    scheduler.add_job("manual", interval_seconds=999, callback=job_fn)

    await scheduler.run_once("manual")
    assert count == 1


@pytest.mark.asyncio
async def test_cron_disable():
    count = 0

    async def job_fn():
        nonlocal count
        count += 1

    scheduler = CronScheduler()
    scheduler.add_job("disabled", interval_seconds=0.05, callback=job_fn)
    scheduler.disable_job("disabled")

    await scheduler.start()
    await asyncio.sleep(0.15)
    await scheduler.stop()

    assert count == 0


@pytest.mark.asyncio
async def test_cron_enable_after_disable():
    count = 0

    async def job_fn():
        nonlocal count
        count += 1

    scheduler = CronScheduler()
    scheduler.add_job("toggle", interval_seconds=0.05, callback=job_fn)
    scheduler.disable_job("toggle")
    scheduler.enable_job("toggle")

    await scheduler.start()
    await asyncio.sleep(0.15)
    await scheduler.stop()

    assert count >= 1


def test_cron_get_job():
    scheduler = CronScheduler()
    scheduler.add_job("a", interval_seconds=10, callback=lambda: None)

    job = scheduler.get_job("a")
    assert job is not None
    assert job.name == "a"
    assert job.run_count == 0

    assert scheduler.get_job("missing") is None


def test_cron_remove_job():
    scheduler = CronScheduler()
    scheduler.add_job("a", interval_seconds=10, callback=lambda: None)
    scheduler.remove_job("a")
    assert scheduler.get_job("a") is None
