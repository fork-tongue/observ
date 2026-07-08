# Computed State

`computed()` creates derived state: a function whose result is cached, and automatically invalidated when any of the reactive state it depends on changes.

```python
from observ import computed, reactive

state = reactive({"first": "Ada", "last": "Lovelace"})

@computed
def full_name():
    return f"{state['first']} {state['last']}"

print(full_name())  # "Ada Lovelace"
```

`computed` can be used as a decorator (as above) or called directly with a function:

```python
full_name = computed(lambda: f"{state['first']} {state['last']}")
```

The wrapped function must take no arguments.

## Lazy evaluation

A computed does no work until its value is requested. When a dependency changes, the cached value is merely marked *dirty* — the function is re-evaluated on the next call, and only then:

```python
@computed
def expensive():
    print("crunching...")
    return sum(state["numbers"])

state = reactive({"numbers": list(range(1000))})

expensive()          # prints: crunching...
expensive()          # cached: no print
state["numbers"].append(1)  # only marks it dirty: no print
expensive()          # prints: crunching...
```

This means you can define lots of derived state without worrying about paying for state you never read.

## Composing computeds

Computed functions can freely use other computed functions, forming a dependency graph. Only the affected parts of the graph are invalidated:

```python
@computed
def subtotal():
    return sum(item["price"] for item in state["items"])

@computed
def total():
    return subtotal() + state["shipping"]
```

Changing `state["shipping"]` invalidates `total` but leaves the cached `subtotal` intact.

Watchers can watch computed functions like any other function — see [Watchers](watchers.md).

## Rules for computed functions

* **Don't mutate reactive state** inside a computed function. Computed state should be a pure derivation; mutating state from within one can cause update cycles. If you need side effects, use a [watcher](watchers.md) instead.
* By default a computed *deep-watches* its result (`deep=True`): when the function returns a container, changes nested anywhere inside that container also invalidate the computed. Pass `computed(deep=False)` to depend only on the state that was actually read while evaluating, which can be cheaper for large data structures.
