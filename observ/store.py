from functools import partial, wraps
from typing import Callable, Generic, TypeVar

import patchdiff

from .proxy import (
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
            current = to_raw(self.state)
            fn(self, *args, **kwargs)
            ops, reverse_ops = patchdiff.diff(current, self.state)
            # If ops and reverse_ops are empty, that means
            # that there are no actual changes to record
            if self._strict or ops or reverse_ops:
                if not ops and not reverse_ops:
                    raise RuntimeError(
                        "Calling mutation didn't result in any change to state"
                    )

                self._past.append((ops, reverse_ops))
                self._future.clear()
        finally:
            self.state = readonly_state

    return inner


def computed(_fn=None, *, deep=True):
    def decorator_computed(fn: T) -> T:
        fn.deep = deep
        fn.decorator = "computed"
        return fn

    if _fn is None:
        return decorator_computed
    return decorator_computed(_fn)


S = TypeVar("S")


class Store(Generic[S]):
    """
    Store that tracks mutations to state in order to enable undo/redo functionality
    """

    def __init__(self, state: S, strict=True):
        """
        Creates a store with the given state as the initial state.
        When `strict` is False, calling mutations that do not result
        in an actual change will be ignored.
        """
        self._strict = strict
        self._present = reactive(state)
        self._past = shallow_reactive([])
        self._future = shallow_reactive([])
        self.state = readonly(state)
        self._computed_props = {}

        for method_name in dir(self):
            method = getattr(self, method_name)
            fn = getattr(method, "__func__", None)
            if fn and getattr(fn, "decorator", None) == "computed":
                self._computed_props[method_name] = computed_expression(
                    partial(fn, self), deep=fn.deep
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
        return len(self._past) > 0

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

        ops, reverse_ops = self._past.pop()
        patchdiff.iapply(self._present, reverse_ops)
        self._future.append((ops, reverse_ops))

    def redo(self):
        """
        Redoes the next mutation
        """
        if not self.can_redo:
            return

        ops, reverse_ops = self._future.pop()
        patchdiff.iapply(self._present, ops)
        self._past.append((ops, reverse_ops))
