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
    # WRITE

    def append(self, value):
        retval = super().append(value)
        get_dep(self).notify()
        return retval

    def clear(self):
        retval = super().clear()
        get_dep(self).notify()
        return retval

    def extend(self, value):
        retval = super().extend(value)
        get_dep(self).notify()
        return retval

    def insert(self, index, value):
        retval = super().insert(index, value)
        get_dep(self).notify()
        return retval

    def pop(self, index):
        retval = super().pop(index)
        get_dep(self).notify()
        return retval

    def remove(self, value):
        retval = super().remove(value)
        get_dep(self).notify()
        return retval

    def reverse(self):
        retval = super().reverse()
        get_dep(self).notify()
        return retval

    def sort(self, *args, **kwargs):
        retval = super().sort(*args, **kwargs)
        get_dep(self).notify()
        return retval

    def __setattr__(self, name, value):
        retval = super().__setattr__(name, value)
        get_dep(self).notify()
        return retval

    def __setitem__(self, key, value):
        old_value = super().__getitem__(key)
        retval = super().__setitem__(key, value)
        if old_value != value:
            get_dep(self).notify()
        return retval

    def __add__(self, value):
        retval = super().__add__(value)
        get_dep(self).notify()
        return retval

    def __delattr__(self, name):
        retval = super().__delattr__(name)
        get_dep(self).notify()
        return retval

    def __delitem__(self, key):
        retval = super().__delitem__(key)
        get_dep(self).notify()
        return retval

    def __iadd__(self, value):
        retval = super().__iadd__(value)
        get_dep(self).notify()
        return retval

    def __imul__(self, value):
        retval = super().__imul__(value)
        get_dep(self).notify()
        return retval

    # READ

    def count(self, value):
        if Dep.stack:
            get_dep(self).depend()
        return super().count(value)

    def index(self, *args, **kwargs):
        if Dep.stack:
            get_dep(self).depend()
        return super().index(*args, **kwargs)

    def copy(self):
        if Dep.stack:
            get_dep(self).depend()
        return super().copy()

    def __getitem__(self, s):
        if Dep.stack:
            get_dep(self).depend()
        return super().__getitem__(s)

    def __hash__(self):
        if Dep.stack:
            get_dep(self).depend()
        return super().__hash__()

    def __contains__(self, key):
        if Dep.stack:
            get_dep(self).depend()
        return super().__contains__(key)

    def __eq__(self, value):
        if Dep.stack:
            get_dep(self).depend()
        return super().__eq__(value)

    def __ge__(self, value):
        if Dep.stack:
            get_dep(self).depend()
        return super().__ge__(value)

    def __getattribute__(self, name):
        if Dep.stack and name != '__deps__':
            get_dep(self).depend()
        return super().__getattribute__(name)

    def __gt__(self, value):
        if Dep.stack:
            get_dep(self).depend()
        return super().__gt__(value)

    def __le__(self, value):
        if Dep.stack:
            get_dep(self).depend()
        return super().__le__(value)

    def __lt__(self, value):
        if Dep.stack:
            get_dep(self).depend()
        return super().__lt__(value)

    def __mul__(self, value):
        if Dep.stack:
            get_dep(self).depend()
        return super().__mul__(value)

    def __ne__(self, value):
        if Dep.stack:
            get_dep(self).depend()
        return super().__ne__(value)

    def __rmul__(self, value):
        if Dep.stack:
            get_dep(self).depend()
        return super().__rmul__(value)

    def __iter__(self):
        if Dep.stack:
            get_dep(self).depend()
        return super().__iter__()

    def __len__(self):
        if Dep.stack:
            get_dep(self).depend()
        return super().__len__()

    def __repr__(self):
        if Dep.stack:
            get_dep(self).depend()
        return super().__repr__()

    def __str__(self):
        if Dep.stack:
            get_dep(self).depend()
        return super().__str__()


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
