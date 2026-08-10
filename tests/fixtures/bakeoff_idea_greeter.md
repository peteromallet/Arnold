# B6 parity bakeoff idea — tiny greeter module

Add a small Python module `tools/greeter.py` to the project root with:

1. A `greet(name: str, punctuation: str = "!") -> str` function that returns
   `Hello, <name><punctuation>` (e.g. `greet("Ada") == "Hello, Ada!"`).
2. A `__main__` block that prints `greet("world")`.
3. A `tests/test_greeter.py` file with three passing pytest cases: the default
   greeting, a custom punctuation, and an empty name edge case.

Keep the change minimal: two new files, no edits to existing files, no new
dependencies. The test suite must pass with `python -m pytest tests/test_greeter.py -q`.
