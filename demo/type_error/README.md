# Demo Fixture: Type Error (Traceback Mode)

A function that tries to increment a string age value without converting it to `int` first.

## Bug
```python
# snippet.py
def parse_age(value):
    return value + 1  # TypeError: str + int
```

## Traceback
```
TypeError: can only concatenate str (not "int") to str
```

This fixture uses **traceback mode** instead of pytest. The agent will:
1. Run `snippet.py` in the sandbox.
2. Verify the fix by checking that the TypeError no longer occurs and the exit code is 0.

## Expected Fix
Change `value + 1` to `int(value) + 1`.

## Repo Mode Demo

For testing repository mode, use this small public Python repo:
- **URL:** `https://github.com/simple-login/app`
- **Test command:** `pytest tests/ -q --disable-warnings`

> Note: Repo mode requires the cloned repo to have its dependencies available.
> For a simpler demo, use snippet mode with the fixtures above.
