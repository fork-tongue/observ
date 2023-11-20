import asyncio

from .scheduler import scheduler


def init(mode="asyncio"):
    if mode == "qt":
        scheduler.register_qt()

    if mode == "asyncio":
        scheduler.register_asyncio()


def loop_factory():
    loop = asyncio.new_event_loop()
    if hasattr(asyncio, "eager_task_factory"):
        loop.set_task_factory(asyncio.eager_task_factory)
    return loop
