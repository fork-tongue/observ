import asyncio

from .scheduler import scheduler


def init(mode="asyncio", loop=None):
    """
    Integrate the scheduler with an event loop, so that watcher
    callbacks are batched and run on the loop. Supported modes are
    'asyncio' (the default), 'qt' and 'rendercanvas'. A specific
    loop object can be given for the 'asyncio' and 'rendercanvas'
    modes.
    """
    if mode == "qt":
        scheduler.register_qt()

    elif mode == "asyncio":
        scheduler.register_asyncio(loop)

    elif mode == "rendercanvas":
        if loop is None:
            raise TypeError("A loop object is required for the 'rendercanvas' mode")
        scheduler.register_rendercanvas(loop)


def loop_factory():
    """
    Creates a new asyncio event loop with the eager task factory
    enabled (Python 3.12+), which reduces the latency of the tasks
    that observ schedules for async functions and callbacks.
    """
    loop = asyncio.new_event_loop()
    eager_task_factory = getattr(asyncio, "eager_task_factory", None)
    if eager_task_factory is not None:
        loop.set_task_factory(eager_task_factory)
    return loop
