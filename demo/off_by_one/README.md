# Demo Fixture: Off-by-one Error

A function that finds the last element of a list but uses `len(items)` instead of `len(items) - 1`, causing an IndexError.

## Bug
```python
# snippet.py
def last_element(items):
    return items[len(items)]
```

## Test
```python
# test_snippet.py
def test_last_element():
    from snippet import last_element
    assert last_element([10, 20, 30]) == 30
    assert last_element(["a"]) == "a"
```

## Expected Fix
Change `items[len(items)]` to `items[len(items) - 1]` (or `items[-1]`).
