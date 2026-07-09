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
* **Fully typed** — a [PEP 561](https://peps.python.org/pep-0561/) typed package, checked with [ty](https://github.com/astral-sh/ty) in CI.

## Quick start

```
pip install observ
```

```python
from observ import computed, reactive, watch

state = reactive({
    "todos": [
        {"title": "groceries", "done": False},
        {"title": "dishes", "done": True},
    ],
})

@computed
def progress():
    done = sum(todo["done"] for todo in state["todos"])
    return f"{done}/{len(state['todos'])} done"

watcher = watch(progress, lambda new: print(new), sync=True)

# Mutate the plain dicts and lists you already have —
# observ sees every change, no matter how deeply nested:
state["todos"][0]["done"] = True                            # prints: 2/2 done
state["todos"].append({"title": "laundry", "done": False})  # prints: 2/3 done

# ...but you only ever react when a *result* actually changes:
state["todos"][1]["title"] = "do the dishes"                # (no print)
```

No subclasses to inherit, no observable fields to declare, no signals to wire up: `reactive()` takes your existing data, and dependencies are tracked automatically simply by using it.

Continue with the [Quick Start tutorial](https://fork-tongue.github.io/observ/getting-started/quick-start/), or dive into the [Guide](https://fork-tongue.github.io/observ/guide/reactivity/) and [API Reference](https://fork-tongue.github.io/observ/reference/api/).

## Related projects

* [Collagraph](https://github.com/fork-tongue/collagraph): reactive user interfaces in Python, built on top of observ.
* [Reliev](https://github.com/fork-tongue/reliev): the store (with undo/redo support) that used to be part of observ.
* [Patchdiff](https://github.com/fork-tongue/patchdiff): diffing and patching for plain Python data structures — the same dicts, lists and sets you'd wrap with observ.
