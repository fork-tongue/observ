import asyncio
import sys

import pytest

from observ import reactive, watch, watch_effect


@pytest.fixture
def plain_loop():
    loop = asyncio.new_event_loop()
    asyncio.get_event_loop_policy().set_event_loop(loop)
    return loop


def test_asyncio_watch_callback(plain_loop):
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


def test_asyncio_watch_expression_not_supported(plain_loop):
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
def eager_loop(plain_loop):
    # only python>=3.12
    if not getattr(asyncio, "eager_task_factory", None):
        yield
        return

    old_factory = plain_loop.get_task_factory()
    plain_loop.set_task_factory(asyncio.eager_task_factory)
    try:
        yield plain_loop
    finally:
        plain_loop.set_task_factory(old_factory)


def test_asyncio_watch_effect_eager_loop(eager_loop):
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


def test_asyncio_watch_effect_plain_loop(plain_loop):
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

    watcher = plain_loop.run_until_complete(_coroutine())  # noqa: F841

    with pytest.xfail("doesn't work without eager loop"):
        assert called == 1
