"""
Benchmarks for different traverse implementations.

These benchmarks test various optimization strategies for the traverse function
which is used for deep watching of reactive data structures.
"""

import pytest

from observ import reactive
from observ.watcher import traverse


def create_shallow_structure(size=100):
    """Create a flat dictionary with many keys."""
    data = {f"key_{i}": f"value_{i}" for i in range(size)}
    return reactive(data)


def create_deep_structure(depth=100):
    """Create a deeply nested dictionary."""
    obj = {"value": "leaf"}
    for i in range(depth):
        obj = {"level": i, "child": obj}
    return reactive(obj)


def create_wide_structure(breadth=10, depth=3):
    """Create a wide tree structure."""

    def make_tree(current_depth):
        if current_depth >= depth:
            return {"leaf": True}
        return {f"child_{i}": make_tree(current_depth + 1) for i in range(breadth)}

    data = make_tree(0)
    return reactive(data)


def create_list_structure(size=100):
    """Create a list with nested lists."""
    data = [{"index": i, "data": [i, i + 1, i + 2]} for i in range(size)]
    return reactive(data)


def create_cyclic_structure(use_reactive=False):
    """Create a structure with cycles."""
    obj = {"name": "root"}
    child = {"name": "child", "parent": obj}
    obj["child"] = child
    obj["self"] = obj
    return reactive(obj)


def create_mixed_structure(size=50):
    """Create a structure mixing dicts, lists, and sets."""
    data = {
        "dict": {f"k{i}": i for i in range(size)},
        "list": [i for i in range(size)],
        "nested": [{"index": i, "values": [i * 2, i * 3]} for i in range(size // 5)],
        "set": {i for i in range(size)},
    }
    return reactive(data)


def create_large_flat_list(size=1000):
    """Create a large flat list."""
    data = list(range(size))
    return reactive(data)


def create_matrix_structure(rows=50, cols=50):
    """Create a matrix-like structure (list of lists)."""
    data = [[i * cols + j for j in range(cols)] for i in range(rows)]
    return reactive(data)


# Parametrize all tests with different implementations
@pytest.mark.benchmark(group="traverse_shallow")
def test_traverse_shallow(benchmark):
    """Benchmark traverse on shallow structure (many keys at one level)
    with reactive proxies."""
    structure = create_shallow_structure(size=100)
    benchmark(traverse, structure)


@pytest.mark.benchmark(group="traverse_deep")
def test_traverse_deep(benchmark):
    """Benchmark traverse on deep structure (linear chain) with reactive proxies."""
    structure = create_deep_structure(depth=100)
    benchmark(traverse, structure)


@pytest.mark.benchmark(group="traverse_wide")
def test_traverse_wide(benchmark):
    """Benchmark traverse on wide tree structure with reactive proxies."""
    structure = create_wide_structure(breadth=10, depth=3)
    benchmark(traverse, structure)


@pytest.mark.benchmark(group="traverse_list")
def test_traverse_list(benchmark):
    """Benchmark traverse on list structure with reactive proxies."""
    structure = create_list_structure(size=100)
    benchmark(traverse, structure)


@pytest.mark.benchmark(group="traverse_cyclic")
def test_traverse_cyclic(benchmark):
    """Benchmark traverse on cyclic structure with reactive proxies."""
    structure = create_cyclic_structure(use_reactive=True)
    benchmark(traverse, structure)


@pytest.mark.benchmark(group="traverse_mixed")
def test_traverse_mixed(benchmark):
    """Benchmark traverse on mixed structure with reactive proxies."""
    structure = create_mixed_structure(size=50)
    benchmark(traverse, structure)


@pytest.mark.benchmark(group="traverse_large_flat")
def test_traverse_large_flat_list(benchmark):
    """Benchmark traverse on large flat list with reactive proxies."""
    structure = create_large_flat_list(size=1000)
    benchmark(traverse, structure)


@pytest.mark.benchmark(group="traverse_matrix")
def test_traverse_matrix(benchmark):
    """Benchmark traverse on matrix structure (list of lists) with reactive proxies."""
    structure = create_matrix_structure(rows=50, cols=50)
    benchmark(traverse, structure)


# Stress test with very large structures using reactive proxies
@pytest.mark.benchmark(group="traverse_stress")
def test_traverse_stress_large_shallow(benchmark):
    """Stress test with large shallow structure using reactive proxies."""
    structure = create_shallow_structure(size=1000)
    benchmark(traverse, structure)


@pytest.mark.benchmark(group="traverse_stress")
def test_traverse_stress_large_mixed(benchmark):
    """Stress test with large mixed structure using reactive proxies."""
    structure = create_mixed_structure(size=200)
    benchmark(traverse, structure)
