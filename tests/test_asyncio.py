import asyncio

import pytest

from observ import reactive, watch, watch_effect


def flush(loop):
    while pending := asyncio.all_tasks(loop):
        loop.run_until_complete(asyncio.gather(*pending))


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


@pytest.fixture
def eager_loop(plain_loop):
    # only python>=3.12
    if not getattr(asyncio, "eager_task_factory", None):
        pytest.skip()
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
    completed = 0

    async def _expr():
        nonlocal called, completed
        called += 1
        len_a = len(a)  # noqa: F841
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        completed += 1

    async def _coroutine():
        return watch_effect(_expr, sync=True)

    watcher = eager_loop.run_until_complete(_coroutine())  # noqa: F841
    assert called == 1
    assert completed == 0
    flush(eager_loop)
    assert called == 1
    assert completed == 1

    async def _coroutine():
        a.append(3)

    eager_loop.run_until_complete(_coroutine())
    assert called == 2
    assert completed == 1
    flush(eager_loop)
    assert called == 2
    assert completed == 2


def test_asyncio_watch_effect_plain_loop(plain_loop):
    a = reactive([1, 2])
    called = 0
    completed = 0

    async def _expr():
        nonlocal called, completed
        called += 1
        len_a = len(a)  # noqa: F841
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        completed += 1

    async def _coroutine():
        return watch_effect(_expr, sync=True)

    watcher = plain_loop.run_until_complete(_coroutine())  # noqa: F841
    assert called == 1
    assert completed == 0
    flush(plain_loop)
    assert called == 1
    assert completed == 1

    async def _coroutine():
        a.append(3)

    plain_loop.run_until_complete(_coroutine())
    # nothing happens because the coroutine did not run eagerly
    # (synchronously until its first await statement) which
    # means that the reactive datastructures were not accessed
    # while the Dep tracking mechanism was active
    assert called == 1
    assert completed == 1
    flush(plain_loop)
    assert called == 1
    assert completed == 1


def test_asyncio_watch_effect_method(eager_loop):
    a = reactive([1, 2])
    called = 0
    completed = 0

    class Foo:
        async def _expr(self):
            nonlocal called, completed
            called += 1
            len_a = len(a)  # noqa: F841
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            completed += 1

    foo = Foo()

    async def _coroutine():
        return watch_effect(foo._expr, sync=True)

    watcher = eager_loop.run_until_complete(_coroutine())  # noqa: F841
    assert called == 1
    assert completed == 0
    flush(eager_loop)
    assert called == 1
    assert completed == 1

    async def _coroutine():
        a.append(3)

    eager_loop.run_until_complete(_coroutine())
    assert called == 2
    assert completed == 1
    flush(eager_loop)
    assert called == 2
    assert completed == 2


def test_asyncio_watch_effect_from_sync(eager_loop):
    async def _expr():
        pass

    with pytest.raises(RuntimeError):
        watch_effect(_expr, sync=True)

    flush(eager_loop)


def test_asyncio_watcher_sync_callback_from_async(eager_loop):
    a = reactive([1, 2])
    called = 0

    async def _callback():
        nonlocal called
        called += 1

    def _expr():
        return len(a)

    async def _coroutine():
        return watch(_expr, _callback, immediate=True, sync=True)

    watcher = eager_loop.run_until_complete(_coroutine())  # noqa: F841
    assert called == 1
    a.append(3)
    flush(eager_loop)
    assert called == 2
