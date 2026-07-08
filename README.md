[![PyPI version](https://badge.fury.io/py/observ.svg)](https://badge.fury.io/py/observ)
[![CI status](https://github.com/fork-tongue/observ/workflows/CI/badge.svg)](https://github.com/fork-tongue/observ/actions)

# Observ 👁

Observ is a Python port of [Vue.js](https://vuejs.org/)' [computed properties and watchers](https://vuejs.org/guide/essentials/reactivity-fundamentals.html). It is event loop/framework agnostic and has no dependencies so it can be used in any project targeting Python >= 3.9.

Observ provides the following two benefits for stateful applications:

1) You no longer need to manually invalidate and recompute state (e.g. by dirty flags):
    * computed state is invalidated automatically
    * computed state is lazily re-evaluated
2) You can react to changes in state (computed or not), enabling unidirectional flow:
    * _state changes_ lead to _view changes_ (e.g. a state change callback updates a UI widget)
    * the _view_ triggers _input events_ (e.g. a mouse event is triggered in the UI)
    * _input events_ lead to _state changes_ (e.g. a mouse event updates the state)

## Quick start

Install observ with pip/pipenv/poetry/uv:

`pip install observ`

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

## Documentation

Full documentation — including a tutorial, guides on reactivity, computed state, watchers and event loop integration, and the complete API reference — is available at:

**[fork-tongue.github.io/observ](https://fork-tongue.github.io/observ)**

Check out [`examples/`](https://github.com/fork-tongue/observ/tree/master/examples) for runnable examples using Qt and rendercanvas.

## Related projects

* [Collagraph](https://github.com/fork-tongue/collagraph): reactive user interfaces in Python, built on top of observ.
* [Reliev](https://github.com/fork-tongue/reliev): the store (with undo/redo support) that used to be part of observ.
