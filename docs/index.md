# Observ 👁

Observ is a Python port of [Vue.js](https://vuejs.org/)' [computed properties and watchers](https://vuejs.org/guide/essentials/reactivity-fundamentals.html). It is event loop/framework agnostic and has no dependencies, so it can be used in any project targeting Python >= 3.9.

Observ provides two benefits for stateful applications:

1. You no longer need to manually invalidate and recompute state (e.g. by dirty flags):
    * computed state is invalidated automatically
    * computed state is lazily re-evaluated
2. You can react to changes in state (computed or not), enabling unidirectional flow:
    * _state changes_ lead to _view changes_ (e.g. a state change callback updates a UI widget)
    * the _view_ triggers _input events_ (e.g. a mouse event is triggered in the UI)
    * _input events_ lead to _state changes_ (e.g. a mouse event updates the state)

## A taste of observ

```python
from observ import computed, reactive, watch

state = reactive({"count": 0, "items": []})

@computed
def total():
    return state["count"] + len(state["items"])

def on_total_changed(new, old):
    print(f"total changed from {old} to {new}")

watcher = watch(total, on_total_changed, sync=True)

state["items"].append("thing")  # prints: total changed from 0 to 1
state["count"] += 1             # prints: total changed from 1 to 2
```

No dirty flags, no manual notification: mutating the state through the reactive proxy is enough for observ to figure out what changed and who needs to know about it.

## Where to go next

* Follow the [Quick Start](getting-started/quick-start.md) to learn the core concepts in a few minutes.
* Read the [Guide](guide/reactivity.md) for an in-depth look at reactivity, computed state, watchers and scheduling.
* Browse the [API Reference](reference/api.md) for the complete public API.
* Curious how it all works? The [Internals](internals/architecture.md) section explains the architecture under the hood.
* Check out the [Examples](examples/integrations.md) to see observ integrated with Qt and rendercanvas.

## Related projects

* [Collagraph](https://github.com/fork-tongue/collagraph): reactive user interfaces in Python, built on top of observ.
* [Reliev](https://github.com/fork-tongue/reliev): the store (with undo/redo support) that used to be part of observ.
