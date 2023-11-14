import asyncio
import sys

import pytest

from observ import reactive, watch, watch_effect


@pytest.fixture
def ensure_loop():
    loop = asyncio.new_event_loop()
    asyncio.get_event_loop_policy().set_event_loop(loop)
    return loop


def test_asyncio_watch_callback(ensure_loop):
    a = reactive([1, 2])
    called = 0

    async def _callback():
        nonlocal called
        await asyncio.sleep(0)
        called += 1

    watcher = watch(lambda: len(a), _callback, sync=True)
    assert not watcher.dirty
    assert called == 0

    a.append(3)
    assert called == 1
    assert len(a) == 3


def test_asyncio_watch_expression_not_supported(ensure_loop):
    a = reactive([1, 2])

    async def _expr():
        len_a = len(a)
        await asyncio.sleep(0)
        return len_a

    # should raise runtimeerror
    # either because python<3.12 or because
    # task factory is not eager
    with pytest.raises(RuntimeError):
        watcher = watch(_expr, sync=True)  # noqa: F841


@pytest.fixture
def eager_loop(ensure_loop):
    # only python>=3.12
    if not getattr(asyncio, "eager_task_factory", None):
        yield
        return

    loop = ensure_loop
    old_factory = loop.get_task_factory()
    loop.set_task_factory(asyncio.eager_task_factory)
    try:
        yield loop
    finally:
        loop.set_task_factory(old_factory)


def test_asyncio_watch_effect(eager_loop):
    a = reactive([1, 2])
    called = 0

    async def _expr():
        nonlocal called
        len_a = len(a)  # noqa: F841
        await asyncio.sleep(0)
        called += 1

    if sys.version_info < (3, 12, 0):
        with pytest.raises(RuntimeError):
            watcher = watch_effect(_expr, sync=True)
        return

    async def _coroutine():
        return watch_effect(_expr, sync=True)

    watcher = eager_loop.run_until_complete(_coroutine())  # noqa: F841
    assert called == 1

    async def _coroutine():
        a.append(3)

    eager_loop.run_until_complete(_coroutine())

    assert called == 2
    assert len(a) == 3
