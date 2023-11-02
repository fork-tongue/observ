"""
watchers perform dependency tracking via functions acting on
observable datastructures, and optionally trigger callback when
a change is detected.
"""
from __future__ import annotations

from collections.abc import Container
from functools import partial, wraps
import inspect
from itertools import count
from typing import Any, Callable, Optional, TypeVar
from weakref import ref, WeakSet

from .dep import Dep
from .dict_proxy import DictProxyBase
from .list_proxy import ListProxyBase
from .proxy import Proxy
from .scheduler import scheduler
from .set_proxy import SetProxyBase


T = TypeVar("T", bound=Callable[[], Any])


def watch(
    fn: Callable[[], Any] | Proxy | list[Proxy],
    callback: Optional[Callable] = None,
    sync: bool = False,
    deep: bool | None = None,
    immediate: bool = False,
):
    watcher = Watcher(fn, sync=sync, lazy=False, deep=deep, callback=callback)
    if immediate:
        watcher.dirty = True
        watcher.evaluate()
        if watcher.callback:
            watcher.run_callback(watcher.value, None)
    return watcher


watch_effect = partial(watch, immediate=True, deep=True, callback=None)


def computed(_fn=None, *, deep=True):
    def decorator_computed(fn: T) -> T:
        """
        Create a watcher for an expression.
        Note: make sure fn doesn't need any arguments to run
        and that no reactive state is changed within the expression
        """
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


def traverse(obj, seen=None):
    """
    Recursively traverse the whole tree to make sure
    that all values have been 'get'
    """
    # we are only interested in traversing a fixed set of types
    # otherwise we can just exit
    if isinstance(obj, (dict, DictProxyBase)):
        val_iter = iter(obj.values())
    elif isinstance(obj, (list, ListProxyBase, set, SetProxyBase, tuple)):
        val_iter = iter(obj)
    else:
        return
    # track which objects we have already seen to support(!) full traversal
    # of datastructures with cycles
    # NOTE: a set would provide faster containment checks
    # but these objects are not hashable (except for tuple) because they are mutable
    # converting everything to a hashable thing (because nothing is mutated during
    # traversal) is an option but way more expensive than just using a list
    if seen is None:
        seen = []
    seen.append(obj)
    for v in val_iter:
        if (
            isinstance(
                v, (dict, DictProxyBase, list, ListProxyBase, set, SetProxyBase, tuple)
            )
        ) and v not in seen:
            traverse(v, seen=seen)


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


class Watcher:
    def __init__(
        self,
        fn: Callable[[], Any] | Proxy | list[Proxy],
        sync: bool = False,
        lazy: bool = True,
        deep: bool | None = None,
        callback: Callable = None,
    ) -> None:
        """
        sync: Ignore the scheduler
        lazy: Only reevalutate when value is requested
        deep: Deep watch the watched value
        callback: Method to call when value has changed
        """
        self.id = next(_ids)
        if callable(fn):
            if is_bound_method(fn):
                self.fn = weak(fn.__self__, fn.__func__)
            else:
                self.fn = fn
        else:
            self.fn = lambda: fn
            # Default to deep watching when watching a proxy
            # or a list of proxies
            if deep is None:
                deep = True
        self._deps, self._new_deps = WeakSet(), WeakSet()

        self.sync = sync
        if is_bound_method(callback):
            self.callback = weak(callback.__self__, callback.__func__)
        else:
            self.callback = callback
        self.deep = bool(deep)
        self.lazy = lazy
        self.dirty = self.lazy
        self.value = None if self.lazy else self.get()
        self._number_of_callback_args = None

    def update(self) -> None:
        if self.lazy:
            self.dirty = True
        elif self.sync:
            self.run()
        else:
            scheduler.queue(self)

    def evaluate(self) -> None:
        self.value = self.get()
        self.dirty = False

    def run(self) -> None:
        """Called by scheduler"""
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
        if self._number_of_callback_args == 1:
            self.callback(new)
            return
        if self._number_of_callback_args == 2:
            self.callback(new, old)
            return
        if self._number_of_callback_args == 0:
            self.callback()
            return

        try:
            self._run_callback(new)
            self._number_of_callback_args = 1
            return
        except WrongNumberOfArgumentsError:
            pass

        try:
            self._run_callback()
            self._number_of_callback_args = 0
            return
        except WrongNumberOfArgumentsError:
            pass

        self._run_callback(new, old)
        self._number_of_callback_args = 2

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
            self.callback(*args)
        except TypeError as e:
            frames = inspect.trace()
            try:
                if len(frames) != 1:
                    raise
                raise WrongNumberOfArgumentsError(str(e)) from e
            finally:
                del frames

    def get(self) -> Any:
        Dep.stack.append(self)
        try:
            value = self.fn()
            if self.deep:
                traverse(value)
        finally:
            Dep.stack.pop()
            self.cleanup_deps()
        return value

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
    nr_arguments = len(sig.parameters)

    if nr_arguments == 1:

        @wraps(method)
        def wrapped():
            if this := weak_obj():
                return method(this)

        return wrapped
    elif nr_arguments == 2:

        @wraps(method)
        def wrapped(new):
            if this := weak_obj():
                return method(this, new)

        return wrapped
    elif nr_arguments == 3:

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
