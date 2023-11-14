import asyncio
import sys

import pytest

from observ import reactive, watch


def test_asyncio_watch_callback():
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


@pytest.fixture
def asyncio_eager():
    # only python>=3.12
    if not getattr(asyncio, "eager_task_factory", None):
        yield
        return

    loop = asyncio.get_event_loop_policy().get_event_loop()
    old_factory = loop.get_task_factory()
    loop.set_task_factory(asyncio.eager_task_factory)
    try:
        yield
    finally:
        loop.set_task_factory(old_factory)


def test_asyncio_watch_expression_not_supported():
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


def test_asyncio_watch_expression(asyncio_eager):
    a = reactive([1, 2])
    called = 0

    async def _expr():
        len_a = len(a)
        await asyncio.sleep(0)
        return len_a

    def _callback():
        nonlocal called
        called += 1

    if sys.version_info < (3, 12, 0):
        with pytest.raises(RuntimeError):
            watcher = watch(_expr, _callback, sync=True)
        return

    watcher = watch(_expr, _callback, sync=True)
    assert not watcher.dirty
    assert called == 0

    a.append(3)
    assert called == 1
    assert len(a) == 3
