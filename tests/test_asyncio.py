import asyncio

import pytest

from observ import reactive, watch, watch_effect


def flush(loop):
    while pending := asyncio.all_tasks(loop):
        loop.run_until_complete(asyncio.gather(*pending))


def create_plain_loop():
    loop = asyncio.new_event_loop()
    asyncio.get_event_loop_policy().set_event_loop(loop)
    return loop


@pytest.fixture
def plain_loop():
    return create_plain_loop()


def create_eager_loop():
    # only python>=3.12
    if not hasattr(asyncio, "eager_task_factory"):
        pytest.skip()

    loop = create_plain_loop()
    loop.set_task_factory(asyncio.eager_task_factory)
    return loop


@pytest.fixture
def eager_loop():
    return create_eager_loop()


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


def test_asyncio_watch_effect_from_sync(plain_loop):
    a = reactive([1, 2])
    called = 0

    async def _expr():
        nonlocal called
        len_a = len(a)  # noqa: F841
        await asyncio.sleep(0)
        called += 1

    watcher = watch_effect(_expr, sync=True)  # noqa: F841
    assert called == 1
    a.append(3)
    assert called == 2


def test_asyncio_watcher_sync_callback_from_async(plain_loop):
    a = reactive([1, 2])
    called = 0

    async def _callback():
        nonlocal called
        called += 1

    def _expr():
        return len(a)

    async def _coroutine():
        return watch(_expr, _callback, immediate=True, sync=True)

    watcher = plain_loop.run_until_complete(_coroutine())  # noqa: F841
    assert called == 1
    a.append(3)
    flush(plain_loop)
    assert called == 2


w_testcases = []
for create_loop in [create_plain_loop, create_eager_loop]:
    for expr_async in [False, True]:
        for callback_async in [False, True]:
            for create_async in [False, True]:
                for write_async in [False, True]:
                    idstr = "-".join(
                        [
                            "plain_loop"
                            if create_loop is create_plain_loop
                            else "eager_loop",
                            "expr_async" if expr_async else "expr_sync",
                            "callback_async" if callback_async else "callback_sync",
                            "create_async" if create_async else "create_sync",
                            "write_async" if write_async else "write_sync",
                        ]
                    )
                    w_testcases.append(
                        pytest.param(
                            create_loop,
                            expr_async,
                            callback_async,
                            create_async,
                            write_async,
                            id=idstr,
                        )
                    )


@pytest.mark.parametrize(
    "create_loop,expr_async,callback_async,create_async,write_async", w_testcases
)
def test_asyncio_watcher_multi(
    create_loop, expr_async, callback_async, create_async, write_async
):
    loop = create_loop()
    a = reactive([1, 2])
    called = 0
    completed = 0

    if expr_async:

        async def _expr():
            return len(a)

    else:

        def _expr():
            return len(a)

    if callback_async:

        async def _callback():
            nonlocal called, completed
            called += 1
            await asyncio.sleep(0)
            completed += 1

    else:

        def _callback():
            nonlocal called, completed
            called += 1
            completed += 1

    if create_async:

        async def _create():
            return watch(_expr, _callback, sync=True)

        _ = loop.run_until_complete(_create())
    else:
        _ = watch(_expr, _callback, sync=True)

    # ASSERTS pt I
    assert (called, completed) == (0, 0)
    flush(loop)
    assert (called, completed) == (0, 0)

    if write_async:

        async def _write():
            a.append(3)

        loop.run_until_complete(_write())
    else:
        a.append(3)

    # ASSERTS pt II
    if (
        create_loop is create_plain_loop
        and not expr_async
        and callback_async
        and write_async
    ):
        assert (called, completed) == (1, 0)
    elif (
        create_loop is create_plain_loop
        and expr_async
        and callback_async
        and not create_async
        and write_async
    ):
        assert (called, completed) == (1, 0)
    elif create_loop is create_plain_loop and expr_async and create_async:
        assert (called, completed) == (0, 0)
    elif (
        create_loop is create_eager_loop and expr_async and create_async and write_async
    ):
        assert (called, completed) == (0, 0)
    else:
        assert (called, completed) == (1, 1)
    flush(loop)
    if create_loop is create_plain_loop and expr_async and create_async:
        assert (called, completed) == (0, 0)
    elif (
        create_loop is create_eager_loop and expr_async and create_async and write_async
    ):
        assert (called, completed) == (0, 0)
    else:
        assert (called, completed) == (1, 1)


we_testcases = []
for create_loop in [create_plain_loop, create_eager_loop]:
    for expr_async in [False, True]:
        for create_async in [False, True]:
            for write_async in [False, True]:
                idstr = "-".join(
                    [
                        "plain_loop"
                        if create_loop is create_plain_loop
                        else "eager_loop",
                        "expr_async" if expr_async else "expr_sync",
                        "create_async" if create_async else "create_sync",
                        "write_async" if write_async else "write_sync",
                    ]
                )
                we_testcases.append(
                    pytest.param(
                        create_loop, expr_async, create_async, write_async, id=idstr
                    )
                )


@pytest.mark.parametrize(
    "create_loop,expr_async,create_async,write_async", we_testcases
)
def test_asyncio_watcheffect_multi(create_loop, expr_async, create_async, write_async):
    loop = create_loop()
    a = reactive([1, 2])
    called = 0
    completed = 0

    if expr_async:

        async def _expr():
            nonlocal called, completed
            called += 1
            _ = len(a)
            await asyncio.sleep(0)
            completed += 1

    else:

        def _expr():
            nonlocal called, completed
            called += 1
            _ = len(a)
            completed += 1

    if create_async:

        async def _create():
            return watch_effect(_expr, sync=True)

        _ = loop.run_until_complete(_create())
    else:
        _ = watch_effect(_expr, sync=True)

    # ASSERTS pt I
    if create_loop is create_plain_loop and expr_async and create_async:
        assert (called, completed) == (1, 0)
    else:
        assert (called, completed) == (1, 1)
    flush(loop)
    assert (called, completed) == (1, 1)

    if write_async:

        async def _write():
            a.append(3)

        loop.run_until_complete(_write())
    else:
        a.append(3)

    # ASSERTS pt II
    if create_loop is create_plain_loop and expr_async and create_async:
        assert (called, completed) == (1, 1)
    elif (
        create_loop is create_plain_loop
        and expr_async
        and not create_async
        and write_async
    ):
        assert (called, completed) == (2, 1)
    else:
        assert (called, completed) == (2, 2)
    flush(loop)
    if create_loop is create_plain_loop and expr_async and create_async:
        assert (called, completed) == (1, 1)
    else:
        assert (called, completed) == (2, 2)
