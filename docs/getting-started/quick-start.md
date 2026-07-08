# Quick Start

This tutorial walks through the three core concepts of observ: **reactive state**, **computed state** and **watchers**. All examples on this page are complete and runnable.

## Reactive state

Wrap a plain data structure with `reactive()` to make it observable:

```python
from observ import reactive

state = reactive({"name": "World", "todos": ["hello"]})
```

`state` looks and feels exactly like the dict you passed in — you can index it, iterate over it, call `.items()` on it, and so on. But behind the scenes it is a *proxy* that records which parts of the state are read, and notifies interested parties when parts of it change. This works for arbitrarily nested structures of dicts, lists, sets and tuples.

## Watchers

A watcher runs a function, records every piece of reactive state that the function touches, and triggers a callback whenever any of those dependencies change:

```python
from observ import reactive, watch

state = reactive({"name": "World"})

def greeting():
    return f"Hello {state['name']}!"

def greeting_changed(new, old):
    print(f"was: {old!r}, now: {new!r}")

watcher = watch(greeting, greeting_changed, sync=True)

state["name"] = "Python"  # prints: was: 'Hello World!', now: 'Hello Python!'
```

Note that `greeting` doesn't declare its dependencies anywhere: observ discovers that it depends on `state["name"]` simply by running it. If a later run touches different state, the dependencies are updated automatically.

Keep a reference to the returned watcher object: when it is garbage collected, the callback stops firing.

!!! note "Why `sync=True`?"

    By default, watcher callbacks are not called immediately, but batched and deduplicated by a scheduler that hooks into your event loop (asyncio, Qt, rendercanvas, ...). In a plain script without an event loop there is nothing to schedule on, so `sync=True` tells the watcher to fire straight away. In a real application you would leave it off and call `init()` once at startup — see [Scheduling](../guide/scheduling.md).

## Computed state

`computed()` derives new state from existing state. The result is cached and only recomputed when a dependency changed — lazily, at the moment somebody asks for the value:

```python
from observ import computed, reactive

state = reactive({"todos": ["groceries", "dishes"]})

@computed
def todo_count():
    print("computing!")
    return len(state["todos"])

print(todo_count())  # prints: computing! 2
print(todo_count())  # prints: 2  (cached, no recompute)

state["todos"].append("laundry")

print(todo_count())  # prints: computing! 3
```

Computed state is itself watchable, and computeds can depend on other computeds, forming an efficient dependency graph that only recomputes the parts that were actually invalidated:

```python
from observ import computed, reactive, watch

state = reactive({"todos": ["groceries"]})

@computed
def todo_count():
    return len(state["todos"])

@computed
def all_done():
    return todo_count() == 0

watcher = watch(all_done, lambda done: print(f"all done: {done}"), sync=True)

state["todos"].pop()  # prints: all done: True
```

## Where to go next

You now know the essentials! To go deeper:

* [Reactivity](../guide/reactivity.md) — what can and cannot be made reactive, and how proxies behave.
* [Watchers](../guide/watchers.md) — all `watch()` options, callback signatures and watcher lifecycle.
* [Scheduling](../guide/scheduling.md) — integrating with asyncio, Qt or rendercanvas event loops.
