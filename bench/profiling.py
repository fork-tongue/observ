from observ import reactive


@profile
def main():
    obj = reactive({})
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
