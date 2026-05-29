"""Tests for copy/deepcopy behavior of Proxy objects."""

import copy

import pytest

from observ import reactive
from observ.proxy import Proxy


@pytest.mark.parametrize(
    "value, expected_type",
    [
        ({"a": 1, "b": 2}, dict),
        ([1, 2, 3], list),
        ({1, 2, 3}, set),
    ],
)
def test_deepcopy_reactive_returns_plain_type(value, expected_type):
    data = reactive(value)
    result = copy.deepcopy(data)
    assert type(result) is expected_type
    assert not isinstance(result, Proxy)
    assert result == value


def test_deepcopy_is_independent():
    data = reactive({"a": [1, 2]})
    result = copy.deepcopy(data)
    result["a"].append(3)
    data["a"].pop()
    assert data["a"] == [1]


def test_copy_reactive_dict_returns_plain_dict():
    data = reactive({"a": 1})
    result = copy.copy(data)
    assert type(result) is dict
    assert not isinstance(result, Proxy)
    assert result == {"a": 1}


def test_deepcopy_nested_proxies_returns_plain_data():
    data = reactive({"nested": {"inner": [1, 2, 3]}})
    # Access nested to ensure they become proxies
    inner = data["nested"]["inner"]
    assert isinstance(inner, Proxy)
    result = copy.deepcopy(data)
    assert type(result) is dict
    assert type(result["nested"]) is dict
    assert type(result["nested"]["inner"]) is list
