from observ import reactive, watch


def noop():
    pass


# @profile
def main():
    obj = reactive({})

    watch(obj, callback=noop, deep=True, sync=True)

    obj["bar"] = "baz"
    obj["quux"] = "quuz"
    obj.update(
        {
            "bar": "foo",
            "quazi": "var",
        }
    )
    del obj["bar"]
    _ = obj["quux"]
    obj.clear()


if __name__ == "__main__":
    main()
