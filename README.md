[![PyPI version](https://badge.fury.io/py/observ.svg)](https://badge.fury.io/py/observ)
[![CI status](https://github.com/Korijn/observ/workflows/CI/badge.svg)](https://github.com/Korijn/observ/actions)

# Observ 👁

Observ is a Python port of [Vue.js](https://vuejs.org/)' [computed properties and watchers](https://v3.vuejs.org/api/basic-reactivity.html). It is completely event loop/framework agnostic and has no dependencies so it can be used in any project targeting Python >= 3.6.

Observ provides the following two benefits for stateful applications:

1) You no longer need to manually invalidate and recompute state (e.g. by dirty flags):
    * computed state is invalidated automatically
    * computed state is lazily re-evaluated
2) You can react to changes in state (computed or not), enabling unidirectional flow:
    * _state changes_ lead to _view changes_ (e.g. a state change callback updates a UI widget)
    * the _view_ triggers _input events_ (e.g. a mouse event is triggered in the UI)
    * _input events_ lead to _state changes_ (e.g. a mouse event updates the state)

## API

`from observ import reactive, computed, watch`

* `state = reactive(state)`

Observe nested structures of dicts, lists, tuples and sets. Returns an observable proxy that wraps the state input object.

* `watcher = watch(func, callback, deep=False, immediate=False)`

React to changes in the state accessed in `func` with `callback(old_value, new_value)`. Returns a watcher object. `del`elete it to disable the callback.

* `wrapped_func = computed(func)`

Define computed state based on observable state with `func` and recompute lazily. Returns a wrapped copy of the function which only recomputes the output if any of the state it depends on becomes dirty. Can be used as a function decorator.

## Quick start and example

Install observ with pip/pipenv/poetry:

`pip install observ`

Check out [`examples/observe_qt.py`](https://github.com/Korijn/observ/blob/master/examples/observe_qt.py) for a simple example using observ.

## Caveats

Observ keeps references to the object passed to the `reactive` in order to keep track of dependencies and proxies for that object. When the object that is passed into `reactive` is not managed by other code, then observ should cleanup its references automatically when the proxy is destroyed. However, if there is another reference to the original object, then observ will only release its own reference when the garbage collector is run and all other references to the object are gone.
