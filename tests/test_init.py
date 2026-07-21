import asyncio

from observ import init, loop_factory, scheduler


def flush(loop):
    while pending := asyncio.all_tasks(loop):
        loop.run_until_complete(asyncio.gather(*pending))


def test_init_asyncio():
    try:
        init(mode="asyncio")
        assert scheduler.request_flush == scheduler.request_flush_asyncio
    finally:
        scheduler.register_request_flush(scheduler.request_flush_raise)


def test_loop_factory():
    async def _coroutine():
        return asyncio.get_running_loop()

    actual_loop = asyncio.run(_coroutine(), loop_factory=loop_factory)
    assert actual_loop.get_task_factory() is asyncio.eager_task_factory
