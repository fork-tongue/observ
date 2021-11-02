import copy
from functools import partial
from typing import Callable, Collection, TypeVar

from .observables import (
    reactive,
    readonly,
    shallow_reactive,
    to_raw,
)
from .watcher import computed as computed_expression


T = TypeVar("T", bound=Callable)


registry = {}


def mutation(fn: T) -> T:
    registry[fn] = "mutation"
    return fn


def computed(fn: T) -> T:
    registry[fn] = "computed"
    return fn


class Store:
    """
    Store that tracks mutations to state in order to enable undo/redo functionality
    """

    def __init__(self, state: Collection):
        """
        Creates a store with the given state as the initial state.
        """
        self._present = reactive(state)
        # Because we can't work with diff patches (yet) we'll have to copy
        # over the whole state. When triggering undo/redo, we'll therefore
        # trigger all the watchers / computed expressions...
        self._past = shallow_reactive([copy.deepcopy(to_raw(state))])
        self._future = shallow_reactive([])
        self.state = readonly(state)
        self._computed_props = {}

        for method_name in dir(self):
            method = getattr(self, method_name)
            if not hasattr(method, "__func__") or method.__func__ not in registry:
                continue

            wrap_type = registry[method.__func__]
            if wrap_type == "mutation":
                method = partial(self.commit, method)
                setattr(self, method_name, method)
            elif wrap_type == "computed":
                self._computed_props[method_name] = computed_expression(
                    partial(method.__func__, self)
                )

    def __getattribute__(self, name):
        if name != "_computed_props":
            fn = self._computed_props.get(name)
            if fn:
                return fn()
        return super().__getattribute__(name)

    def commit(self, fn: Callable, *args, **kwargs):
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
