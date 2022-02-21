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

    def notify(self, ops=None) -> None:
        for sub in sorted(self._subs, key=lambda s: s.id):
            sub.update(ops)


class Path:
    stack = []

    @classmethod
    def put(cls, obj, component):
        # Maybe try to start building the path from the
        # object that is returned in the lambda? Is that
        # even possible?
        if (id(obj), component) in cls.stack:
            # Should maybe clear from that index?
            cls.stack.clear()
        cls.stack.append((id(obj), component))
        print("put", cls.stack)
        # breakpoint()

    @classmethod
    def pop(cls):
        if len(cls.stack):
            cls.stack.pop()
        # breakpoint()
        print("pop", cls.stack)
