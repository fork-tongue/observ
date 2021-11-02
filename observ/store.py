import copy
from functools import partial, wraps
from typing import Callable, Collection, TypeVar

from .observables import (
    reactive,
    readonly,
    shallow_reactive,
    to_raw,
)
from .watcher import computed as computed_expression


T = TypeVar("T", bound=Callable)


def mutation(fn: T) -> T:
    @wraps(fn)
    def inner(self, *args, **kwargs):
        readonly_state = self.state
        self.state = self._present
        try:
            fn(self, *args, **kwargs)
            self._past.append(copy.deepcopy(to_raw(self._present)))
            self._future.clear()
        finally:
            self.state = readonly_state

    return inner


# Keep a registry of methods that are wrapped with 'computed'
registry = set()


def computed(fn: T) -> T:
    # Add the method to the registry for bookkeeping
    # Store.__init__ uses the registry to see which methods have
    # been decorated with 'computed' and makes proper computed
    # expressions for those methods.
    registry.add(fn)
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
            fn = getattr(method, "__func__", None)
            if fn and fn in registry:
                self._computed_props[method_name] = computed_expression(
                    partial(fn, self)
                )

    def __getattribute__(self, name):
        super_getattribute = super().__getattribute__
        fn = super_getattribute("_computed_props").get(name)
        if fn:
            # Immediately run the computed expression in order to
            # make it behave like a property on the Store
            return fn()
        return super_getattribute(name)

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
        if not self.can_undo:
            return
        current = self._past.pop()
        previous = self._past[-1]

        self._present.update(previous)
        self._future.append(copy.deepcopy(to_raw(current)))

    def redo(self):
        """
        Redoes the next mutation
        """
        if not self.can_redo:
            return
        first = self._future.pop()

        self._present.update(first)
        self._past.append(copy.deepcopy(to_raw(self._present)))
