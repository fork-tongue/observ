[![PyPI version](https://badge.fury.io/py/observ.svg)](https://badge.fury.io/py/observ)

# Observ 👁

Observ is a Python port of [Vue.js](https://vuejs.org/)' [computed properties and watchers](https://vuejs.org/v2/guide/computed.html). It is completely event loop/framework agnostic and has no dependencies so it can be used in any project targeting Python >= 3.6.

# Quick start

Install observ in your Celery workers via pip/pipenv/poetry:

`pip install observ`

Example usage:

```python
>>> from observ import observe, computed, watch
>>> a = observe({"foo": 5})
>>> def my_callback(old_value, new_value):
...     print(f"{old_value} became {new_value}!")
...
>>> watch(lambda: a["foo"], callback=my_callback)
<observ.Watcher object at 0x00000190DAA7EB70>
>>> a["foo"] = 6
5 became 6!
>>>
>>> @computed
... def my_computed_property():
...     print("running")
...     return 5 * a["foo"]
...
>>> assert my_computed_property() == 30
running
>>> assert my_computed_property() == 30
>>>
>>> a["foo"] = 7
6 became 7!
>>> assert my_computed_property() == 35
running
>>> assert my_computed_property() == 35
```
