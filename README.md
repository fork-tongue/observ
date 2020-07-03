[![PyPI version](https://badge.fury.io/py/observ.svg)](https://badge.fury.io/py/observ)

# Observ 👁

Observ is a Python port of [Vue.js](https://vuejs.org/)' [computed properties and watchers](https://vuejs.org/v2/guide/computed.html). It is completely event loop/framework agnostic and has no dependencies so it can be used in any project targeting Python >= 3.6.

## API

`from observ import observe, computed, watch`

* `state = observe(state)`

Observe nested structures of dicts, lists, tuples and sets. Returns an observable clone of the state input object.

* `watch(func, callback, deep=False, immediate=False)`

React to changes in the state accessed in `func` with `callback(old_value, new_value)`. Returns a watcher object that can be `del`eted to disable the callback.

* `func = computed(func)`

Define computed state based on observable state with `func` and recompute lazily. Returns a wrapped copy of the function which only recomputes the output if any of the state it depends on becomes dirty. Can be used as a function decorator.

## Quick start and example

Install observ with pip/pipenv/poetry:

`pip install observ`

Example usage:

```python
>>> from observ import observe, computed, watch
>>>
>>> a = observe({"foo": 5})
>>>
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
>>>
>>> @computed                                
... def second_computed_property():          
...     print("running")                     
...     return 5 * my_computed_property()    
...                                          
>>> assert second_computed_property() == 175 
running                                      
running                                      
>>> assert second_computed_property() == 175 
>>>
>>> a["foo"] = 8                             
7 became 8!                                  
>>> assert second_computed_property() == 200 
running                                      
running                                      
>>> assert second_computed_property() == 200 
```
