from observ import observe, computed, watch

a = observe({"foo": 5})

def my_callback(old_value, new_value):
    print(f"{old_value} became {new_value}!")

watch(lambda: a["foo"], my_callback)

a["foo"] = 6

@computed
def my_computed_property():
    print("running")
    return 5 * a["foo"]

assert my_computed_property() == 30
assert my_computed_property() == 30

a["foo"] = 7
assert my_computed_property() == 35
assert my_computed_property() == 35

@computed
def second_computed_property():
    print("running")
    return 5 * my_computed_property()

assert second_computed_property() == 175

a["foo"] = 8
assert second_computed_property() == 200
