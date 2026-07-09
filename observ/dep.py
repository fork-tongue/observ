"""
Deps implement the classic observable pattern, and
are attached to observable datastructures.
"""

from __future__ import annotations

from operator import attrgetter
from typing import TYPE_CHECKING, ClassVar
from weakref import WeakSet

if TYPE_CHECKING:
    from .watcher import Watcher

sub_id = attrgetter("id")


class Dep:
    __slots__ = ("__weakref__", "_subs")
    stack: ClassVar[list[Watcher]] = []

    def __init__(self) -> None:
        self._subs: WeakSet[Watcher] | None = None

    def add_sub(self, sub: Watcher) -> None:
        if self._subs is None:
            self._subs = WeakSet()
        self._subs.add(sub)

    def remove_sub(self, sub: Watcher) -> None:
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
            for sub in sorted(self._subs, key=sub_id):
                sub.update()
