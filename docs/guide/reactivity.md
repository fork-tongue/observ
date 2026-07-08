# Reactivity

The heart of observ is `reactive()`: it wraps a plain data structure in a *proxy* that behaves exactly like the original object, but tracks reads and writes.

```python
from observ import reactive

state = reactive({
    "user": {"name": "Ada"},
    "todos": ["invent programming"],
    "tags": {"science", "history"},
})
```

When a watcher (or computed) runs a function, every read through a proxy — a key lookup, an iteration, a `len()` call — registers that piece of state as a dependency of the function. Every write — item assignment, `append()`, `add()`, `del`, and so on — notifies the watchers that depend on it.

## What can be made reactive

Reactivity is supported for the plain data types:

* `dict`
* `list`
* `set`
* `tuple`

These can be nested arbitrarily. Nesting is handled *lazily*: a proxy for a nested container is only created at the moment you access it.

```python
state = reactive({"nested": {"deep": [1, 2, 3]}})

nested = state["nested"]  # nested is itself a reactive proxy
deep = nested["deep"]     # and so is this list
```

Since tuples are immutable, they are not proxied themselves; instead a new tuple is returned in which each *element* is made reactive.

Plain values (`None`, `bool`, `int`, `float`, `str`, `bytes`) cannot be proxied and are returned as-is. If you want a reactive scalar value, use [`ref`](#refs).

!!! warning "Exact types only"

    Only the exact types `dict`, `list`, `set` and `tuple` are proxied — subclasses (and other objects, like dataclass instances) are deliberately not. If a custom class instance lives inside your state, reads and writes on *its* attributes are invisible to observ.

## Proxies are transparent and consistent

A proxy supports the complete interface of its target, so you can pass it to code that isn't aware of observ. Requesting a proxy for the same object twice yields the same proxy, so identity semantics within your state tree are preserved:

```python
data = {"key": "value"}
assert reactive(data) is reactive(data)
```

Calling `reactive()` on something that is already a reactive proxy returns it unchanged.

`copy.copy()` and `copy.deepcopy()` on a proxy return a copy of the raw target, not a new proxy.

## Refs

Because plain values can't be proxied, observ provides `ref()` as a convenience for a single reactive value. A ref is simply a reactive dict with a single `"value"` key:

```python
from observ import ref, watch

count = ref(0)

watcher = watch(lambda: count["value"], lambda new: print(f"count: {new}"), sync=True)

count["value"] += 1  # prints: count: 1
```

## From proxy back to plain data

Use `to_raw()` to recursively strip all proxies from a data structure, e.g. before serializing it or handing it off to code that should not trigger dependency tracking:

```python
from observ import reactive, to_raw

state = reactive({"items": [1, 2, 3]})
plain = to_raw(state)
assert type(plain) is dict
```

!!! warning "Keep no references to the raw data"

    Observ tracks proxies per raw object. The best practice is to call `reactive()` on freshly constructed data and keep **no references** to the raw input — work with the proxy only. See [Gotchas and Best Practices](gotchas.md) for the details.
