"""
watchers perform dependency tracking via functions acting on
observable datastructures, and optionally trigger callback when
a change is detected.
"""
from collections.abc import Container
from itertools import count
from typing import Any
from weakref import WeakSet

from .dep import Dep
from .scheduler import scheduler


def traverse(obj):
    _traverse(obj, set())


def _traverse(obj, seen):
    seen.add(id(obj))
    if isinstance(obj, dict):
        val_iter = iter(obj.values())
    elif isinstance(obj, (list, tuple, set)):
        val_iter = iter(obj)
    else:
        val_iter = iter(())
    for v in val_iter:
        if isinstance(v, Container) and id(v) not in seen:
            _traverse(v, seen)


# Every Watcher gets a unique ID which is used to
# keep track of the order in which subscribers will
# be notified
_ids = count()


class Watcher:
    def __init__(self, fn, sync=False, lazy=True, deep=False, callback=None) -> None:
        """
        sync: Ignore the scheduler
        lazy: Only reevalutate when value is requested
        deep: Deep watch the watched value
        callback: Method to call when value has changed
        """
        self.id = next(_ids)
        self.fn = fn
        self._deps, self._new_deps = WeakSet(), WeakSet()

        self.sync = sync
        self.callback = callback
        self.deep = deep
        self.lazy = lazy
        self.dirty = self.lazy
        self.value = None if self.lazy else self.get()

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
                self.callback(old_value, self.value)

    def get(self) -> Any:
        Dep.stack.append(self)
        try:
            value = self.fn()
        finally:
            if self.deep:
                traverse(value)
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
