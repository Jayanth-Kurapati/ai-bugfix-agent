def test_last_element():
    from snippet import last_element
    assert last_element([10, 20, 30]) == 30
    assert last_element(["a"]) == "a"
