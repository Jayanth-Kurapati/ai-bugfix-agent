# Demo Fixture: Wrong Operator

A simple `add` function that uses subtraction instead of addition.

## Bug
```python
# snippet.py
def add(a, b):
    return a - b  # Should be a + b
```

## Test
```python
# test_snippet.py
def test_add():
    from snippet import add
    assert add(2, 3) == 5
```

## Expected Fix
Change `a - b` to `a + b`.
