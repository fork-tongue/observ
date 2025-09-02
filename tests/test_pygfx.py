import pytest

from observ import reactive

try:
    import pygfx as gfx

    has_pygfx = True
except ImportError:
    has_pygfx = False
pygfx_missing_reason = "Pygfx is not installed"


@pytest.mark.skipif(not has_pygfx, reason=pygfx_missing_reason)
def test_pygfx_geometry_not_wrapped():
    geometry = gfx.sphere_geometry()

    wrapped = reactive(geometry)
    # Assert strict equality to test that it is not wrapped
    assert wrapped is geometry
