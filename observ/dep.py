"""
Deps implement the classic observable pattern, and
are attached to observable datastructures.
"""
from typing import List
from weakref import WeakSet


class Dep:
    stack: List["Watcher"] = []  # noqa: F821

    def __init__(self) -> None:
        self._subs: WeakSet["Watcher"] = WeakSet()  # noqa: F821

    def add_sub(self, sub: "Watcher") -> None:  # noqa: F821
        self._subs.add(sub)

    def remove_sub(self, sub: "Watcher") -> None:  # noqa: F821
        self._subs.remove(sub)

    def depend(self) -> None:
        if self.stack:
            self.stack[-1].add_dep(self)

    def notify(self) -> None:
        for sub in sorted(self._subs, key=lambda s: s.id):
            sub.update()
