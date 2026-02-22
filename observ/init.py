import asyncio

from .scheduler import scheduler


def init(mode="asyncio", loop=None):
    if mode == "qt":
        scheduler.register_qt(loop)

    elif mode == "asyncio":
        scheduler.register_asyncio(loop)

    elif mode == "rendercanvas":
        scheduler.register_rendercanvas(loop)


def loop_factory():
    loop = asyncio.new_event_loop()
    if hasattr(asyncio, "eager_task_factory"):
        loop.set_task_factory(asyncio.eager_task_factory)
    return loop
