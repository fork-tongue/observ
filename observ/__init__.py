__version__ = "0.1.0"


from itertools import count
from typing import Union, Any
from collections.abc import Container
from weakref import WeakSet
from functools import wraps


class Dep:
    stack = []

    def __init__(self) -> None:
        self._subs = WeakSet()

    def add_sub(self, sub: "Watcher") -> None:
        self._subs.add(sub)

    def remove_sub(self, sub: "Watcher") -> None:
        self._subs.remove(sub)

    def depend(self) -> None:
        if self.stack:
            self.stack[-1].add_dep(self)

    def notify(self) -> None:
        for sub in sorted(self._subs, key=lambda s: s.id):
            sub.update()


def get_dep(obj, key=None) -> "Dep":
    """Store Dep objects on the containers they decorate such that
    their lifetimes are linked"""
    if not hasattr(obj, "__deps__"):
        setattr(obj, "__deps__", {})
    if key not in obj.__deps__:
        obj.__deps__[key] = Dep()
    return obj.__deps__[key]


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


_ids = count()


class Watcher:
    def __init__(self, fn, lazy=True, deep=False, callback=None) -> None:
        self.id = next(_ids)
        self.fn = fn
        self._deps, self._new_deps = WeakSet(), WeakSet()

        self.callback = callback
        self.deep = deep
        self.lazy = lazy
        self.dirty = self.lazy
        self.value = None if self.lazy else self.get()

    def update(self) -> None:
        self.dirty = True
        if not self.lazy:
            self.evaluate()

    def evaluate(self) -> None:
        if self.dirty:
            old_value = self.value
            self.value = self.get()
            self.dirty = False
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

    def teardown(self) -> None:
        for dep in self._deps:
            dep.remove_sub(self)

    def __del__(self) -> None:
        self.teardown()


class ObservableDict(dict):
    # TODO cover all important methods
    def __getitem__(self, key: Any) -> Any:
        if Dep.stack:
            get_dep(self, key).depend()
        return super().__getitem__(key)

    def values(self):
        if Dep.stack:
            get_dep(self).depend()
        return super().values()

    def __setitem__(self, key: Any, new_value: Any) -> None:
        value = super().__getitem__(key)
        super().__setitem__(key, new_value)
        if new_value != value:
            get_dep(self, key).notify()
            get_dep(self).notify()


class ObservableList(list):
    # TODO cover all important methods
    def __getitem__(self, key: Any) -> Any:
        if Dep.stack:
            get_dep(self).depend()
        return super().__getitem__(key)

    def __iter__(self):
        if Dep.stack:
            get_dep(self).depend()
        return super().__iter__()

    def __setitem__(self, key: Any, new_value: Any) -> None:
        value = super().__getitem__(key)
        super().__setitem__(key, new_value)
        if new_value != value:
            get_dep(self).notify()


class ObservableSet(set):
    # TODO cover all important methods
    def __contains__(self, obj: Any) -> Any:
        if Dep.stack:
            get_dep(self).depend()
        return super().__contains__(obj)

    def __iter__(self):
        if Dep.stack:
            get_dep(self).depend()
        return super().__iter__()

    def add(self, new_value: Any) -> None:
        is_new = new_value not in self
        super().add(new_value)
        if is_new:
            get_dep(self).notify()


def observe(obj, deep=True):
    if isinstance(obj, dict):
        reactive = ObservableDict(obj)
        if deep:
            for k, v in reactive.items():
                reactive[k] = observe(v)
        return reactive
    elif isinstance(obj, list):
        reactive = ObservableList(obj)
        if deep:
            for i, v in enumerate(reactive):
                reactive[i] = observe(v)
        return reactive
    elif isinstance(obj, tuple):
        reactive = obj  # tuples are immutable
        if deep:
            reactive = tuple(observe(v) for v in reactive)
        return reactive
    elif isinstance(obj, set):
        return (
            ObservableSet(obj) if not deep else ObservableSet(observe(v) for v in obj)
        )
    elif not isinstance(obj, Container):
        return obj
    else:
        raise NotImplementedError(f"Don't know how to make {type(obj)} reactive")


def computed(fn):
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


def watch(fn, callback, deep=False, immediate=False):
    watcher = Watcher(fn, lazy=False, deep=deep, callback=callback)
    if immediate:
        watcher.evaluate()
    return watcher
