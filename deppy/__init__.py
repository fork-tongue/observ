__version__ = "0.1.0"


from itertools import count
from typing import Union, Any
from functools import lru_cache
from collections.abc import Container


_ids = count()


class Dep:
    stack = []

    def __init__(self) -> None:
        self.id = next(_ids)
        self._subs = []

    def add_sub(self, sub: "Watcher") -> None:
        self._subs.append(sub)

    def remove_sub(self, sub: "Watcher") -> None:
        self._subs.remove(sub)

    def depend(self) -> None:
        if self.stack:
            self.stack[-1].add_dep(self)

    def notify(self) -> None:
        for sub in sorted(self._subs, key=lambda s: s.id):
            sub.update()


def get_dep(obj, key=None) -> "Dep":
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


class Watcher:
    def __init__(self, fn, lazy=True, deep=False, callback=None) -> None:
        self.id = next(_ids)
        self.fn = fn
        self._deps, self._new_deps = set(), set()

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


def make_reactive(obj, deep=True):
    if not isinstance(obj, Container):
        return obj
    elif isinstance(obj, dict):
        reactive = ObservableDict(obj)
        if deep:
            for k, v in reactive.items():
                reactive[k] = make_reactive(v)
        return reactive
    elif isinstance(obj, list):
        reactive = ObservableList(obj)
        if deep:
            for i, v in enumerate(reactive):
                reactive[i] = make_reactive(v)
        return reactive
    elif isinstance(obj, tuple):
        reactive = obj  # tuples are immutable
        if deep:
            reactive = tuple(make_reactive(v) for v in reactive)
        return reactive
    elif isinstance(obj, set):
        return (
            ObservableSet(obj)
            if not deep
            else ObservableSet(make_reactive(v) for v in obj)
        )
    else:
        raise NotImplementedError(f"Don't know how to make {type(obj)} reactive")


@lru_cache(maxsize=0)
def cached(fn):
    watcher = Watcher(fn)

    def getter():
        if watcher.dirty:
            watcher.evaluate()
        if Dep.stack:
            watcher.depend()
        return watcher.value

    getter.__watcher__ = watcher
    return getter


if __name__ == "__main__":
    a = make_reactive(
        {"foo": 5, "bar": [6, 7, 8], "quux": 10, "quuz": {"a": 1, "b": 2}}
    )
    execute_count = 0

    def bla():
        global execute_count
        execute_count += 1
        multi = 0
        if a["quux"] == 10:
            multi = a["foo"] * 5
        else:
            multi = a["bar"][-1] * 5
        return multi * a["quuz"]["b"]

    cached_bla = cached(bla)
    assert cached_bla() == 50
    assert cached_bla() == 50
    assert execute_count == 1
    a["quux"] = 25
    assert cached_bla() == 80
    assert cached_bla() == 80
    assert execute_count == 2
    a["quuz"]["b"] = 3
    assert cached_bla() == 120
    assert cached_bla() == 120
    assert execute_count == 3

    def bla2():
        global execute_count
        execute_count += 1
        return a["foo"] * cached_bla()

    cached_bla2 = cached(bla2)
    assert cached_bla2() == 600
    assert cached_bla2() == 600
    assert execute_count == 4
    a["quuz"]["b"] = 4
    assert cached_bla2() == 800
    assert cached_bla2() == 800
    assert execute_count == 6

    called = 0

    def _callback(old_value, new_value):
        global called
        called += 1

    watcher = Watcher(lambda: a["quuz"], lazy=False, deep=True, callback=_callback)
    assert not watcher.dirty
    assert watcher.value == a["quuz"]
    assert len(watcher._deps) == 2
    assert called == 0
    a["quuz"]["b"] = 3
    assert not watcher.dirty
    assert watcher.value == a["quuz"]
    assert len(watcher._deps) == 2
    assert called == 1
