"""
watchers perform dependency tracking via functions acting on
observable datastructures, and optionally trigger callback when
a change is detected.
"""

from __future__ import annotations

import asyncio
import inspect
from collections import deque
from collections.abc import Awaitable, Container
from functools import wraps
from itertools import count
from typing import Any, Callable, Generic, Optional, TypeVar, Union
from weakref import ref

from .dep import Dep
from .proxy import Proxy, proxy
from .proxy_db import proxy_db
from .scheduler import scheduler

T = TypeVar("T")
Watchable = Union[
    Callable[[], T],
    Callable[[], Awaitable[T]],
    T,
]
WatchCallback = Union[Callable[[], Any], Callable[[T], Any], Callable[[T, T], Any]]


def watch(
    fn: Watchable[T],
    callback: WatchCallback[T] | None = None,
    sync: bool = False,
    deep: bool | None = None,
    immediate: bool = False,
) -> Watcher[T]:
    """
    Watch the given function (or proxy) and call the optional callback
    when its value changes. Returns a Watcher object: keep a reference
    to it to keep the watcher alive, and use it to stop, pause and
    resume watching.

    fn: Function to watch. Can also be a proxy (or list of proxies),
        which implies deep watching.
    callback: Method to call when the watched value has changed.
        May accept zero, one (new value) or two (new and old value)
        arguments. When no callback is given, fn is re-evaluated
        when its dependencies change (see also `watch_effect`).
    sync: Run the callback immediately on change instead of
        queueing it on the scheduler.
    deep: Also watch for changes nested inside the watched value.
        Defaults to False when fn is callable, True otherwise.
    immediate: Call the callback right away with the initial value.
    """
    watcher = Watcher(fn, sync=sync, lazy=False, deep=deep, callback=callback)
    if immediate:
        watcher.dirty = True
        watcher.evaluate()
        if watcher.callback:
            watcher.run_callback(watcher.value, None)
    return watcher


def watch_effect(
    fn: Watchable[T],
    sync: bool = False,
    deep: bool = True,
) -> Watcher[T]:
    """
    Run the given function immediately to collect its dependencies
    and re-run it whenever they change. Equivalent to calling `watch`
    without a callback.
    """
    return watch(fn, callback=None, sync=sync, deep=deep, immediate=False)


def computed(_fn: Callable[[], T] | None = None, *, deep=True) -> Callable[[], T]:
    """
    Create derived state from a function: the result is cached and
    only recomputed (lazily) when any of the reactive state it depends
    on has changed. Can be used as a (parameterized) decorator.

    Make sure fn doesn't need any arguments to run and that no
    reactive state is changed within the function.
    """

    def decorator_computed(fn: Callable[[], T]) -> Callable[[], T]:
        watcher = Watcher(fn, deep=deep)

        @wraps(fn)
        def getter():
            if watcher.dirty:
                watcher.evaluate()
            if Dep.stack:
                watcher.depend()
            return watcher.value

        getter.__watcher__ = watcher
        return getter

    if _fn is None:
        return decorator_computed
    return decorator_computed(_fn)


def traverse(obj):
    """
    Non-recursively traverse the whole tree to make sure that the dep of
    every (nested) container has been depended on.

    Instead of iterating through the proxies' trapped iterators (which
    would create a proxy for every visited value), this walks the raw
    targets and registers a dependency on the dep of each container
    directly. That is equivalent: all mutation traps notify the dep of
    the container that they mutate. Containers that don't have an entry
    in the proxy_db yet (raw values nested inside a proxied target) are
    registered along the way, so that mutations through (future) proxies
    for those containers will be seen.

    Every item on the stack is accompanied by a 'tracked' flag, which
    marks containers that are reachable through non-shallow proxies.
    Raw containers that are not reachable through a proxy are not
    tracked (there is no proxy through which they can be mutated), and
    neither are children of shallow proxies (matching the shallow
    iterators, which yield raw values) — unless a child is itself a
    proxy, which always tracks its own dep.

    Track which objects we have already seen (by id) to support(!) full
    traversal of data structures with cycles. Since only raw targets are
    traversed, every seen object is kept alive through the (unchanging)
    tree that is being traversed, so ids can't be reused for the
    duration of this method.
    """
    seen_ids = set()
    stack = deque([(obj, False)])
    db = proxy_db.db
    track = bool(Dep.stack)

    while stack:
        current, tracked = stack.pop()

        if isinstance(current, Proxy):
            # A proxy always tracks its own dep; whether its children
            # are tracked depends on the shallow flag
            tracked = True
            child_tracked = not current.__shallow__
            current = current.__target__
        else:
            child_tracked = tracked

        # We are only interested in traversing a fixed set of types
        # otherwise we can just continue with the next branch
        cls = type(current)
        if cls is dict:
            val_iter = current.values()
        elif cls is list or cls is set or cls is tuple:
            val_iter = current
        else:
            continue

        # Check if we've seen this object before
        obj_id = id(current)
        if obj_id in seen_ids:
            continue

        # Mark as seen
        seen_ids.add(obj_id)

        # Depend on the container's dep (tuples are immutable
        # and have no dep)
        if track and tracked and cls is not tuple:
            weak_dep = db.get(obj_id)
            dep = weak_dep() if weak_dep is not None else None
            if dep is None:
                # Materialize the container in the proxy_db so that it
                # gets a dep to subscribe to. The watcher's strong
                # reference to the dep (through depend) is what keeps
                # the registry entry alive after the transient proxy
                # created here is gone
                dep = proxy(current).__dep__
            dep.depend()

        # Add children to stack
        if current:
            stack.extend((value, child_tracked) for value in val_iter)


# Every Watcher gets a unique ID which is used to
# keep track of the order in which subscribers will
# be notified
_ids = count()


class WrongNumberOfArgumentsError(TypeError):
    """
    Error that is used to signal that the wrong number of arguments is
    used for the callback
    """

    pass


class Watcher(Generic[T]):
    __slots__ = (
        "__weakref__",
        "_active",
        "_deps",
        "_new_deps",
        "_number_of_callback_args",
        "_paused",
        "_pending_update",
        "_tasks",
        "callback",
        "callback_async",
        "deep",
        "dirty",
        "fn",
        "fn_async",
        "id",
        "lazy",
        "no_recurse",
        "sync",
        "value",
    )
    on_created: Optional[Callable[[Watcher[T]], None]] = None
    on_destroyed: Optional[Callable[[Watcher[T]], None]] = None

    def __init__(
        self,
        fn: Watchable[T],
        sync: bool = False,
        lazy: bool = True,
        deep: bool | None = None,
        callback: WatchCallback[T] | None = None,
    ) -> None:
        """
        sync: Ignore the scheduler
        lazy: Only reevaluate when value is requested
        deep: Deep watch the watched value
        callback: Method to call when value has changed
        """
        self.id = next(_ids)
        self._active = True
        self._paused = False
        self._pending_update = False
        if callable(fn):
            if is_bound_method(fn):
                self.fn = weak(fn.__self__, fn.__func__)
            else:
                self.fn = fn
            self.fn_async = inspect.iscoroutinefunction(fn)
        else:
            self.fn = lambda: fn
            self.fn_async = False
            # Default to deep watching when watching a proxy
            # or a list of proxies
            if deep is None:
                deep = True
        # Plain sets: WeakSet operations are implemented in Python and
        # dominate the cost of re-collecting deps on every evaluation.
        # Strong references are safe here: deps don't reference watchers
        # strongly (Dep._subs is a WeakSet). The strong reference is also
        # what keeps the registry entry of a dep's container (and with
        # it, the identity of its deps) alive for exactly as long as
        # this watcher depends on it; deps are released on the next
        # cleanup_deps() or when the watcher is deactivated or collected.
        self._deps, self._new_deps = set(), set()
        self._tasks = set()

        self.sync = sync
        if callable(callback):
            if is_bound_method(callback):
                self.callback = weak(callback.__self__, callback.__func__)
            else:
                self.callback = callback
            self.callback_async = inspect.iscoroutinefunction(callback)
        else:
            self.callback = callback
            self.callback_async = False
        self.no_recurse = callback is None
        self.deep = bool(deep)
        self.lazy = lazy
        self.dirty = self.lazy
        self.value = None if self.lazy else self.get()
        self._number_of_callback_args = None

        if Watcher.on_created:
            Watcher.on_created(self)

    def __call__(self):
        """
        Calling a watcher will stop the watcher and clean up
        any used resource. This can be used when special
        life-cycle management is needed for watchers.
        """
        self.stop()

    def stop(self) -> None:
        """
        Stop the watcher and clean up any used resource.
        Equivalent to calling the watcher object directly.
        """
        self._active = False
        self._paused = False
        self._pending_update = False

        # Clear resources
        self.fn = lambda: ()
        self.fn_async = False
        self.callback = None
        self.callback_async = False
        self.value = None
        self._deps.clear()
        self._new_deps.clear()

    def pause(self) -> None:
        """
        Temporarily pause the watcher: while paused, changes to
        dependencies will not trigger a re-evaluation or callback.
        Resume the watcher with `resume()`.
        """
        self._paused = True

    def resume(self) -> None:
        """
        Resume the watcher after it was paused. If any of its
        dependencies changed while the watcher was paused, it
        will trigger once upon resume.
        """
        if not self._paused:
            return
        self._paused = False
        if self._pending_update:
            self._pending_update = False
            self.update()

    def __del__(self):
        if Watcher.on_destroyed:
            Watcher.on_destroyed(self)

    @property
    def active(self):
        """
        Returns whether this watcher is still active.
        To manually deactivate simply call the watcher object.
        """
        return self._active

    @property
    def paused(self):
        """
        Returns whether this watcher is currently paused.
        Use `pause()` and `resume()` to control this state.
        """
        return self._paused

    def update(self) -> None:
        if self._paused:
            self._pending_update = True
            return

        if self.lazy:
            self.dirty = True
            return

        if Dep.stack and Dep.stack[-1] is self and self.no_recurse:
            return
        if self.sync:
            self.run()
        else:
            scheduler.queue(self)

    def evaluate(self) -> None:
        self.value = self.get()
        self.dirty = False

    def run(self) -> None:
        """Called by scheduler"""
        # Early return for when the watcher has been deactivated
        if not self._active:
            return
        # A watcher that was queued before it was paused should
        # not run until it is resumed
        if self._paused:
            self._pending_update = True
            return
        value = self.get()
        if self.deep or isinstance(value, Container) or value != self.value:
            old_value = self.value
            self.value = value
            if self.callback:
                self.run_callback(self.value, old_value)

    def run_callback(self, new, old) -> None:
        """
        Runs the callback. When the number of arguments is still unknown
        for the callback, it will fall into the try/except contstruct
        to figure out the right number of arguments.
        After running the callback one time, the number of arguments
        is known and the callback can be called with the correct
        amount of arguments.
        """
        if self._number_of_callback_args is not None:
            if self._number_of_callback_args == 1:
                maybe_coro = self.callback(new)
            elif self._number_of_callback_args == 2:
                maybe_coro = self.callback(new, old)
            elif self._number_of_callback_args == 0:
                maybe_coro = self.callback()

        else:
            try:
                maybe_coro = self._run_callback(new)
                self._number_of_callback_args = 1
            except WrongNumberOfArgumentsError:
                pass

            if self._number_of_callback_args is None:
                try:
                    maybe_coro = self._run_callback()
                    self._number_of_callback_args = 0
                except WrongNumberOfArgumentsError:
                    pass

            if self._number_of_callback_args is None:
                maybe_coro = self._run_callback(new, old)
                self._number_of_callback_args = 2

        if self.callback_async and maybe_coro:
            loop = asyncio.get_event_loop()
            if not loop.is_running():
                loop.run_until_complete(maybe_coro)
            else:
                task = loop.create_task(maybe_coro)
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)

    def _run_callback(self, *args) -> None:
        """
        Run the callback with the given arguments. When the callback
        raises a TypeError, check to see if the error results from
        within the callback or from calling the callback with the
        wrong number of arguments.
        Raises WrongNumberOfArgumentsError if callback was called
        with the wrong number of arguments.
        """
        try:
            return self.callback(*args)
        except TypeError as e:
            # figure out if the TypeError was caused by wrong number of arguments
            # by checking the exception's traceback
            wrong_number_of_arguments = False
            try:
                _run_callback_is_top_frame = (
                    e.__traceback__.tb_frame.f_code == self._run_callback.__code__
                )
                _no_lower_frames = e.__traceback__.tb_next is None
                wrong_number_of_arguments = (
                    _run_callback_is_top_frame and _no_lower_frames
                )
            except AttributeError:
                # if there's no traceback we can't figure this out
                pass

            if wrong_number_of_arguments:
                raise WrongNumberOfArgumentsError(str(e)) from e
            else:
                raise

    def get(self) -> Any:
        Dep.stack.append(self)
        try:
            value_or_coro = self.fn()
            if self.fn_async and value_or_coro:
                loop = asyncio.get_event_loop()
                if not loop.is_running():
                    value_or_coro = loop.run_until_complete(value_or_coro)
                else:
                    task = loop.create_task(value_or_coro)
                    self._tasks.add(task)
                    task.add_done_callback(self._tasks.discard)
                    return
            if self.deep:
                traverse(value_or_coro)
        finally:
            Dep.stack.pop()
            self.cleanup_deps()
        return value_or_coro

    def add_dep(self, dep: Dep) -> None:
        if dep not in self._new_deps:
            self._new_deps.add(dep)
            if dep not in self._deps:
                dep.add_sub(self)

    def cleanup_deps(self) -> None:
        for dep in self._deps:
            if dep not in self._new_deps:
                dep.remove_sub(self)
        self._deps, self._new_deps = self._new_deps, self._deps
        self._new_deps.clear()

    def depend(self) -> None:
        """This function is used by other watchers to depend on everything
        this watcher depends on."""
        if Dep.stack:
            for dep in self._deps:
                dep.depend()

    @property
    def fn_fqn(self) -> str:
        return f"{self.fn.__module__}.{self.fn.__qualname__}"


def weak(obj: Any, method: Callable):
    """
    Returns a wrapper for the given method that will only call the method if the
    given object is not garbage collected yet. It does so by using a weakref.ref
    and checking its value before calling the actual method when the wrapper is
    called.
    """
    weak_obj = ref(obj)

    sig = inspect.signature(method)
    iscoro = inspect.iscoroutinefunction(method)
    nr_arguments = len(sig.parameters)

    if nr_arguments == 1:
        if iscoro:

            @wraps(method)
            async def wrapped():
                if this := weak_obj():
                    return await method(this)

        else:

            @wraps(method)
            def wrapped():
                if this := weak_obj():
                    return method(this)

        return wrapped
    elif nr_arguments == 2:
        if iscoro:

            @wraps(method)
            async def wrapped(new):
                if this := weak_obj():
                    return await method(this, new)

        else:

            @wraps(method)
            def wrapped(new):
                if this := weak_obj():
                    return method(this, new)

        return wrapped
    elif nr_arguments == 3:
        if iscoro:

            @wraps(method)
            async def wrapped(new, old):
                if this := weak_obj():
                    return await method(this, new, old)

        else:

            @wraps(method)
            def wrapped(new, old):
                if this := weak_obj():
                    return method(this, new, old)

        return wrapped
    else:
        raise WrongNumberOfArgumentsError(
            "Please use 1, 2 or 3 arguments for callbacks"
        )


def is_bound_method(fn: Callable):
    """
    Returns whether the given function is a bound method.
    """
    return hasattr(fn, "__self__") and hasattr(fn, "__func__")
