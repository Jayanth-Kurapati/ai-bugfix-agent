def test_add():
    from snippet import add
    assert add(2, 3) == 5
    assert add(0, 0) == 0
    assert add(-1, 1) == 0
