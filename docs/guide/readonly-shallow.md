# Readonly and Shallow Proxies

Besides `reactive()`, observ offers three variants that control *who* may write to state and *how deep* the reactivity goes.

## Readonly proxies

`readonly()` returns a proxy through which the state can be read (with full dependency tracking) but not modified. Any attempt to write through it raises a `ReadonlyError`:

```python
from observ import reactive, readonly

state = reactive({"count": 0})
view = readonly(state)

print(view["count"])  # reads work fine, and are tracked

view["count"] = 1     # raises ReadonlyError
```

The readonly proxy wraps the *same* underlying data: changes made through the writable proxy are visible through the readonly proxy and trigger its watchers.

This enables a pattern where one part of your application owns the state and hands out a readonly view to the rest:

```python
class Store:
    def __init__(self, initial_state):
        self._state = reactive(initial_state)
        self.state = readonly(self._state)

    def increment(self):
        self._state["count"] += 1
```

Consumers can watch `store.state` freely but can only modify it through the store's methods, keeping mutations centralized and predictable. (This is essentially what [reliev](https://github.com/fork-tongue/reliev) provides, including undo/redo support.)

## Shallow proxies

By default, reactivity is deep: accessing a nested container through a proxy yields a proxy for that container as well. `shallow_reactive()` limits the reactivity to the *first level* of the wrapped object — nested values are returned raw:

```python
from observ import shallow_reactive

state = shallow_reactive({"big": {"huge": [...]}})

state["big"] = other      # tracked: first-level write
state["big"]["huge"] = x  # NOT tracked: state["big"] is a plain dict
```

This is an escape hatch for performance-sensitive cases: when a value is a large data structure that you replace wholesale rather than mutate in place, shallow reactivity avoids the overhead of proxying every nested access.

`shallow_readonly()` combines both behaviors: a read-only view where only first-level reads are tracked.

## Overview

| Function             | Writable | Deep |
| -------------------- | -------- | ---- |
| `reactive`           | ✅       | ✅   |
| `readonly`           | ❌       | ✅   |
| `shallow_reactive`   | ✅       | ❌   |
| `shallow_readonly`   | ❌       | ❌   |

All four share the same underlying target and bookkeeping: you can create any combination of views for the same data, and writes through a writable view notify watchers on all views.
