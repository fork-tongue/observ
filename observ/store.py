import copy
from functools import partial, wraps
from inspect import signature
from typing import Callable, TypeVar

from .dep import Dep
from .observables import (
    reactive,
    readonly,
    shallow_reactive,
    to_raw,
)
from .watcher import Watcher


T = TypeVar("T", bound=Callable)


registry = {}


def mutation(fn: T) -> T:
    registry[fn] = "mutation"

    @wraps(fn)
    def inner(self, *args, **kwargs):
        return fn(self, *args, **kwargs)

    return inner


def computed(fn: T) -> T:
    parameters = signature(fn).parameters
    if len(parameters) == 1 and "self" in parameters:
        registry[fn] = "computed"

        @wraps(fn)
        def inner(self):
            return fn(self)

        return inner
    else:
        watcher = Watcher(fn)

        @wraps(fn)
        def getter():
            if watcher.dirty:
                watcher.evaluate()
            if Dep.stack:
                watcher.depend()
            return watcher.value

        getter.__watcher__ = watcher
        return getter


registered_computed_props = {}


class Store:
    """
    Store that tracks mutations to state in order to enable undo/redo functionality
    """

    def __init__(self, state):
        self._present = reactive(state)
        # Because we can't work with diff patches (yet) we'll have to copy
        # over the whole state. When triggering undo/redo, we'll therefore
        # trigger all the watchers / computed expressions...
        self._past = shallow_reactive([copy.deepcopy(to_raw(state))])
        self._future = shallow_reactive([])
        self.state = readonly(state)

        computed_props = registered_computed_props.setdefault(id(self), {})
        for method_name in dir(self):
            method = getattr(self, method_name)
            if not hasattr(method, "__wrapped__"):
                continue

            wrap_type = registry.get(method.__wrapped__)
            if wrap_type == "mutation":
                method = partial(self.commit, method)
                setattr(self, method_name, method)
            elif wrap_type == "computed":
                computed_props[method_name] = computed(partial(method.__func__, self))

    def __getattribute__(self, name):
        fn = registered_computed_props[id(self)].get(name)
        if fn:
            return fn()
        return super().__getattribute__(name)

    def commit(self, fn, *args, **kwargs):
        """
        When performing a mutation, clear the future stack
        and update the past with a copy of the new present
        """
        fn(self._present, *args, **kwargs)
        self._past.append(copy.deepcopy(to_raw(self._present)))
        self._future.clear()

    @property
    def can_undo(self) -> bool:
        """
        Returns whether the store can undo some mutation
        """
        return len(self._past) > 1

    @property
    def can_redo(self) -> bool:
        """
        Returns whether the store can redo some mutation
        """
        return len(self._future) > 0

    def undo(self):
        """
        Undoes the last mutation
        """
        assert self.can_undo
        current = self._past.pop()
        previous = self._past[-1]

        self._present.update(previous)
        self._future.append(copy.deepcopy(to_raw(current)))

    def redo(self):
        """
        Redoes the next mutation
        """
        assert self.can_redo
        first = self._future.pop()

        self._present.update(first)
        self._past.append(copy.deepcopy(to_raw(self._present)))


class StoreBackedWidgetMixin:
    def __init__(self, *args, **kwargs):
        super(StoreBackedWidgetMixin, self).__init__(*args, **kwargs)
        # Grap the store from the window property of the parent widget
        self.store = self.parentWidget().window().store


class StoreKeeperMixin:
    def __init__(self, *args, **kwargs):
        store = kwargs.pop("store")
        super(StoreKeeperMixin, self).__init__(*args, **kwargs)
        self.store = store
