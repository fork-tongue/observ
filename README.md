[![PyPI version](https://badge.fury.io/py/observ.svg)](https://pypi.org/project/observ/)
[![CI status](https://github.com/fork-tongue/observ/workflows/CI/badge.svg)](https://github.com/fork-tongue/observ/actions)

# Observ 👁

**Vue.js-style reactivity for Python.** Wrap your state in a reactive proxy, and observ tracks every read and write for you: computed values invalidate themselves, watchers fire when something they depend on changes. No dirty flags, no manual invalidation, no dependency bookkeeping.

📖 **[Documentation](https://fork-tongue.github.io/observ)** · 📦 **[PyPI](https://pypi.org/project/observ/)** · 🧪 **[Examples](https://github.com/fork-tongue/observ/tree/master/examples)** (Qt, rendercanvas)

> ### 🖼️ Building a GUI?
>
> Head straight to **[Collagraph](https://github.com/fork-tongue/collagraph)** — a full-featured, Vue-inspired declarative UI framework built on top of observ. If you're looking for a strong reactive GUI framework for your Python **Qt/PySide** applications, Collagraph is the main entrypoint; observ is the reactivity engine underneath it.

## Why observ?

* **Automatic dependency tracking** — computed state knows exactly what it depends on and lazily re-evaluates only when needed.
* **React to any change** — watch plain state or computed state and build unidirectional data flow: state changes drive view changes, input events drive state changes.
* **Zero dependencies, framework agnostic** — a pure Python library (≥ 3.9) that plugs into any event loop: asyncio, Qt, or your own.

## Quick start

```
pip install observ
```

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

Continue with the [Quick Start tutorial](https://fork-tongue.github.io/observ/getting-started/quick-start/), or dive into the [Guide](https://fork-tongue.github.io/observ/guide/reactivity/) and [API Reference](https://fork-tongue.github.io/observ/reference/api/).

## Related projects

* [Collagraph](https://github.com/fork-tongue/collagraph): reactive user interfaces in Python, built on top of observ.
* [Reliev](https://github.com/fork-tongue/reliev): the store (with undo/redo support) that used to be part of observ.
