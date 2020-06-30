__version__ = "0.1.0"


from itertools import count
from typing import Union, Any


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

    def notify(self):
        for sub in sorted(self._subs, key=lambda s: s.id):
            sub.update()


def get_dep(obj: Any, key: Any) -> "Dep":
    if not hasattr(obj, '__deps__'):
        setattr(obj, '__deps__', {})
    if key not in obj.__deps__:
        obj.__deps__[key] = Dep()
    return obj.__deps__[key]


class Watcher:
    def __init__(self, fn) -> None:
        self.id = next(_ids)
        self.fn = fn
        self._deps, self._new_deps = [], []
        self._dep_ids, self._new_dep_ids = set(), set()
        self.value = None
        self._dirty = True

    def update(self) -> None:
        self._dirty = True

    def evaluate(self) -> None:
        if self._dirty:
            self.value = self.get()
            self._dirty = False
 
    def get(self) -> Any:
        Dep.stack.append(self)
        value = self.fn()
        Dep.stack.pop()
        self.cleanup_deps()
        return value

    def add_dep(self, dep: Dep) -> None:
        if dep.id not in self._new_dep_ids:
            self._new_dep_ids.add(dep.id)
            self._new_deps.append(dep)
            if dep.id not in self._dep_ids:
                dep.add_sub(self)

    def cleanup_deps(self) -> None:
        # unsubscribe to dependencies on which we no longer depend
        for dep in self._deps:
            if dep.id not in self._new_dep_ids:
                dep.remove_sub(self)
        # swap old and new dependency trackers
        self._dep_ids, self._new_dep_ids = self._new_dep_ids, self._dep_ids
        self._deps, self._new_deps = self._new_deps, self._deps
        # clear new dependency lists for next use
        self._new_dep_ids.clear()
        self._new_deps.clear()

    def depend(self) -> None:
        if Dep.stack:
            for dep in self._deps:
                dep.depend()

    def teardown(self) -> None:
        for dep in self._deps:
            dep.remove_sub(self)

    def __del__(self) -> None:
        self.teardown()


class ObservableDict(dict):
    def __getitem__(self, key: Any) -> Any:
        get_dep(self, key).depend()
        return super().__getitem__(key)

    def __setitem__(self, key: Any, new_value: Any) -> None:
        value = super().__getitem__(key)
        if new_value == value:
            return
        super().__setitem__(key, new_value)
        get_dep(self, key).notify()


def cached(fn, _registry={}):
    if fn not in _registry:
        watcher = Watcher(fn)
        def getter():
            watcher.evaluate()
            watcher.depend()
            return watcher.value
        getter.watcher = watcher
        _registry[fn] = getter
    return _registry[fn]


if __name__ == "__main__":
    a = ObservableDict({"foo": 5, "bar": 3, "quux": 10})

    def bla():
        print("bla is running")
        if a["quux"] == 10:
            return a["foo"] * 5
        else:
            return a["bar"] * 5

    cached_bla = cached(bla)
    print(cached_bla())
    print(cached_bla())
    a["foo"] = 10
    print(cached_bla())
    print(cached_bla())

    del cached_bla
