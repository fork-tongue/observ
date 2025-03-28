"""
Deps implement the classic observable pattern, and
are attached to observable datastructures.
"""

from __future__ import annotations

from typing import ClassVar
from weakref import WeakSet


class Dep:
    __slots__ = ("__weakref__", "_subs")
    stack: ClassVar[list["Watcher"]] = []  # noqa: F821

    def __init__(self) -> None:
        self._subs: WeakSet["Watcher"] = None  # noqa: F821

    def add_sub(self, sub: "Watcher") -> None:  # noqa: F821
        if self._subs is None:
            self._subs = WeakSet()
        self._subs.add(sub)

    def remove_sub(self, sub: "Watcher") -> None:  # noqa: F821
        if self._subs:
            self._subs.remove(sub)

    def depend(self) -> None:
        if self.stack:
            self.stack[-1].add_dep(self)

    def notify(self) -> None:
        # just iterating over self._subs even if
        # it is empty is 10x slower
        # than putting this if-statement in front of it
        # because a weakset must acquire a lock on its
        # weak references before iterating
        if self._subs:
            for sub in sorted(self._subs, key=lambda s: s.id):
                sub.update()
