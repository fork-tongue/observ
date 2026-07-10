"""
Tests that verify that observ itself never creates reference cycles:
everything observ allocates must be reclaimable through plain reference
counting, without the help of the cyclic garbage collector. See the
notes on lifetimes in observ/proxy_db.py and docs/guide/gotchas.md.

The garbage collector is disabled during each of these tests, so an
object that would only be reclaimed by the cycle collector shows up as
a weakref that is still alive (or a registry entry that is left
behind) after the last strong reference to it is dropped.
"""

import gc
import weakref

import pytest

from observ import computed, reactive, watch, watch_effect
from observ.proxy_db import proxy_db


@pytest.fixture(autouse=True)
def refcounting_only():
    """
    Disable the garbage collector so that objects can only be
    reclaimed through reference counting.
    """
    gc.collect()
    gc.disable()
    try:
        yield
    finally:
        gc.enable()


def test_proxy_is_reclaimed_by_refcount():
    state = reactive({"count": 0})
    target_id = id(state.__target__)
    weak_proxy = weakref.ref(state)
    weak_dep = weakref.ref(state.__dep__)

    del state

    assert weak_proxy() is None
    assert weak_dep() is None
    assert target_id not in proxy_db.db


def test_nested_proxies_are_reclaimed_by_refcount():
    state = reactive({"items": [{"value": 1}], "tags": {"a", "b"}})
    items = state["items"]
    item = items[0]
    tags = state["tags"]

    proxies = (state, items, item, tags)
    target_ids = [id(p.__target__) for p in proxies]
    weak_proxies = [weakref.ref(p) for p in proxies]
    weak_deps = [weakref.ref(p.__dep__) for p in proxies]

    del state, items, item, tags, proxies

    assert all(r() is None for r in weak_proxies)
    assert all(r() is None for r in weak_deps)
    assert all(target_id not in proxy_db.db for target_id in target_ids)


def test_watcher_is_reclaimed_by_refcount():
    state = reactive({"count": 0})
    calls = []

    watcher = watch(lambda: state["count"], lambda new: calls.append(new), sync=True)
    state["count"] += 1
    assert calls == [1]

    weak_watcher = weakref.ref(watcher)
    del watcher
    assert weak_watcher() is None

    # the dep no longer has any subscribers to notify
    state["count"] += 1
    assert calls == [1]


def test_watch_effect_is_reclaimed_by_refcount():
    state = reactive({"count": 0})
    seen = []

    watcher = watch_effect(lambda: seen.append(state["count"]), sync=True)
    state["count"] += 1
    assert seen == [0, 1]

    weak_watcher = weakref.ref(watcher)
    del watcher
    assert weak_watcher() is None


def test_deep_watcher_keeps_and_releases_registry_entries():
    state = reactive({"nested": {"count": 0}})
    outer_id = id(state.__target__)
    inner_id = id(state.__target__["nested"])

    watcher = watch(state, lambda: None, sync=True)

    # the deep traversal registered a dep for the nested raw dict
    assert outer_id in proxy_db.db
    assert inner_id in proxy_db.db

    # the watcher's strong references to the deps (and the watched
    # proxy, closed over by Watcher.fn) keep the registry entries
    # alive even when the proxy variable goes out of scope
    del state
    assert outer_id in proxy_db.db
    assert inner_id in proxy_db.db

    del watcher
    assert outer_id not in proxy_db.db
    assert inner_id not in proxy_db.db


def test_stopped_watcher_releases_state():
    state = reactive({"count": 0})
    target_id = id(state.__target__)
    weak_dep = weakref.ref(state.__dep__)

    watcher = watch(lambda: state["count"], lambda: None, sync=True)

    watcher.stop()
    # Rebind instead of del: the name is closed over by the watched
    # lambda, and pyflakes would flag that closure as undefined (F821)
    state = None

    # the stopped watcher no longer keeps the state alive: stop()
    # released the watched function (which closed over the proxy)
    # and the collected deps
    assert not watcher.active
    assert weak_dep() is None
    assert target_id not in proxy_db.db


def test_keydep_is_reclaimed_by_refcount():
    state = reactive({"count": 0})
    watcher = watch(lambda: state["count"], lambda: None, sync=True)

    keydeps = state.__dep__.keydeps
    assert keydeps is not None
    assert "count" in keydeps

    # the watcher was the only thing keeping the key's dep alive
    del watcher
    assert "count" not in keydeps


def test_computed_is_reclaimed_by_refcount():
    state = reactive({"count": 1})
    target_id = id(state.__target__)

    @computed
    def double():
        return state["count"] * 2

    assert double() == 2

    weak_watcher = weakref.ref(double.__watcher__)
    # Rebind instead of del: the names are closed over, and pyflakes
    # would flag those closures as undefined (F821)
    double = None
    assert weak_watcher() is None

    state = None
    assert target_id not in proxy_db.db


def test_chained_computed_is_reclaimed_by_refcount():
    state = reactive({"count": 1})
    target_id = id(state.__target__)

    @computed
    def double():
        return state["count"] * 2

    @computed
    def quadruple():
        return double() * 2

    assert quadruple() == 4

    weak_watchers = [
        weakref.ref(double.__watcher__),
        weakref.ref(quadruple.__watcher__),
    ]

    # Rebind instead of del: the names are closed over, and pyflakes
    # would flag those closures as undefined (F821)
    double = quadruple = None
    assert all(r() is None for r in weak_watchers)

    state = None
    assert target_id not in proxy_db.db


@pytest.mark.parametrize("number_of_args", [0, 1, 2])
def test_callback_argument_probing_creates_no_cycle(number_of_args):
    """
    Figuring out the number of callback arguments involves raising and
    catching exceptions and inspecting their tracebacks (see
    Watcher._run_callback), which is a classic way to accidentally
    create frame<->traceback reference cycles that keep the watcher
    alive until the next gc collection.
    """
    state = reactive({"count": 0})
    calls = []

    if number_of_args == 0:

        def cb():
            calls.append(())

    elif number_of_args == 1:

        def cb(new):
            calls.append((new,))

    else:

        def cb(new, old):
            calls.append((new, old))

    watcher = watch(lambda: state["count"], cb, sync=True)
    state["count"] += 1
    assert len(calls) == 1

    weak_watcher = weakref.ref(watcher)
    del watcher
    assert weak_watcher() is None


@pytest.mark.parametrize("exception_class", [RuntimeError, TypeError])
def test_exception_from_callback_creates_no_cycle(exception_class):
    """
    An exception raised from within a callback travels through frames
    that reference the watcher (Watcher._run_callback in particular
    inspects the traceback to tell a wrong signature apart from a
    TypeError raised inside the callback). Once the exception has been
    handled, the watcher must be reclaimable by refcounting alone.
    """
    state = reactive({"count": 0})

    def cb(new):
        raise exception_class("raised from inside the callback")

    watcher = watch(lambda: state["count"], cb, sync=True)

    with pytest.raises(exception_class):
        state["count"] += 1

    weak_watcher = weakref.ref(watcher)
    del watcher
    assert weak_watcher() is None


def test_exception_from_watched_fn_creates_no_cycle():
    state = reactive({"count": 0})

    def fn():
        if state["count"] > 0:
            raise RuntimeError("raised from inside the watched function")
        return state["count"]

    watcher = watch(fn, lambda: None, sync=True)

    with pytest.raises(RuntimeError):
        state["count"] += 1

    weak_watcher = weakref.ref(watcher)
    del watcher
    assert weak_watcher() is None


def test_observ_machinery_creates_no_collectable_cycles():
    """
    Run a scenario that touches most of the observ machinery and
    assert that the cycle collector finds nothing to collect
    afterwards: everything must have been reclaimed by reference
    counting already.
    """

    class Counter:
        count = 0

        def cb(self, new, old):
            type(self).count += 1

    def scenario():
        counter = Counter()
        state = reactive({"items": [1, 2], "nested": {"count": 0}, "tags": {"a"}})
        watchers = [
            watch(lambda: state["nested"]["count"], counter.cb, sync=True),
            watch(state, lambda: None, sync=True),
            watch_effect(lambda: state["items"][0], sync=True),
        ]

        @computed
        def total():
            return state["nested"]["count"] + len(state["items"])

        assert total() == 2
        state["nested"]["count"] += 1
        state["items"].append(3)
        assert total() == 4
        state["tags"].add("b")

        watchers[0].stop()

    # Warm up any caches in the machinery (inspect.signature and
    # friends) so they don't show up in the measured run
    scenario()
    gc.collect()

    scenario()
    assert gc.collect() == 0
