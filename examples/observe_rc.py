"""
Example that demonstrates observ with a small application using rendercanvas.

The canvas events are used to displace individual blocks.
Reactive state is used to maintain a consistent inner distance.
"""

import numpy as np
from rendercanvas.auto import RenderCanvas, loop

from observ import reactive, scheduler, watch

#  Initialize state: the position of the blocks and a delta
state = reactive(
    {
        "delta": (100, 0),
        "pos1": (100, 100),
        "pos2": (200, 100),
        "pos3": (300, 100),
    }
)

# Hook observ to the rendercanvas loop
scheduler.register_rendercanvas(loop)

# Create a canvas and drawing context
canvas = RenderCanvas(title="observ example", update_mode="continuous")
context = canvas.get_bitmap_context()

# The size of the blocks
block_size = 90

# Dragging info. If not None it is (block_index, block_start_pos, pointer_start_pos)
dragging = None

# The bitmap
world = np.zeros((100, 100, 4), np.uint8)


@canvas.add_event_handler("resize")
def on_resize(event):
    global world
    w, h = int(event["width"]), int(event["height"])
    world = np.zeros((h, w, 4), np.uint8)


@canvas.add_event_handler("pointer_down")
def on_pointer_down(event):
    global dragging
    x, y = event["x"], event["y"]
    if event["button"] == 1:
        dragging = None
        for i in (3, 2, 1):
            pos = state[f"pos{i}"]
            if pos[0] < x < pos[0] + block_size and pos[1] < y < pos[1] + block_size:
                dragging = i, pos, (x, y)
                canvas.set_cursor("pointer")
                break


@canvas.add_event_handler("pointer_move")
def on_pointer_move(event):
    x, y = event["x"], event["y"]
    if dragging is not None:
        i, (bx, by), (rx, ry) = dragging
        dx, dy = x - rx, y - ry
        new_x = int(bx + dx)
        new_y = int(by + dy)
        new_x = min(max(new_x, 0), world.shape[1] - block_size)
        new_y = min(max(new_y, 0), world.shape[0] - block_size)
        state[f"pos{i}"] = new_x, new_y


@canvas.add_event_handler("pointer_up")
def on_pointer_up(event):
    global dragging
    if event["button"] == 1:
        dragging = None
        canvas.set_cursor("default")


@canvas.request_draw
def animate():
    world.fill(0)
    world[:, :, 3] = 255

    for key, color in [
        ("pos1", (255, 0, 0, 255)),
        ("pos2", (0, 255, 0, 255)),
        ("pos3", (255, 255, 0, 255)),
    ]:
        x, y = state[key]
        world[y : y + block_size, x : x + block_size] = color

    context.set_bitmap(world)


@watch
def update_12():
    pos1 = state["pos1"]
    pos2 = state["pos2"]
    delta = pos2[0] - pos1[0], pos2[1] - pos1[1]

    state["delta"] = delta
    state["pos3"] = pos2[0] + delta[0], pos2[1] + delta[1]


@watch
def update_23():
    pos2 = state["pos2"]
    pos3 = state["pos3"]
    delta = pos3[0] - pos2[0], pos3[1] - pos2[1]

    state["delta"] = delta
    state["pos1"] = pos2[0] - delta[0], pos2[1] - delta[1]


loop.run()
