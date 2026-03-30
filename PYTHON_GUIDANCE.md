# Python Coding Guidance & Best Practices

This document outlines the core principles for writing high-quality, maintainable, and "Pythonic" code. Use these guidelines when drafting scripts or reviewing AI-generated Python code.

## 1. Core Philosophy (The Zen of Python)
* **Explicit is better than implicit:** Code should clearly state what it is doing. Avoid "magic" behavior.
* **Readability counts:** Code is read much more often than it is written. Write for the human reader.
* **Simple is better than complex:** If a task can be done simply, don't over-engineer it.
* **Flat is better than nested:** Avoid deep nesting of loops and conditionals; use guard clauses to return early.

## 2. Style and Formatting (PEP 8)
* **Indentation:** Always use 4 spaces per indentation level (no tabs).
* **Naming Conventions:**
    * `snake_case` for functions, variables, and modules.
    * `PascalCase` for classes.
    * `UPPER_CASE_SNAKE` for constants.
* **Line Length:** Limit lines to 79–88 characters to ensure readability in side-by-side editors.
* **Whitespace:** Use blank lines to separate functions and classes, and a single space around operators.

## 3. Type Hinting
* **Use Type Annotations:** Always annotate function signatures to improve clarity and catch bugs early.
    * *Example:* `def process_data(items: list[str]) -> int:`
* **Leverage `typing`:** Use `Optional`, `Union`, and `Any` only when necessary, favoring specific types whenever possible.

## 4. Documentation
* **Docstrings:** Every module, class, and function should have a docstring (preferably Google or NumPy style).
* **Comment "Why", not "How":** The code should explain *what* is happening; comments should explain the *reasoning* behind non-obvious logic.

## 5. Clean Logic & Patterns
* **Comprehensions:** Use list, dictionary, and set comprehensions for simple transformations, but revert to for-loops if the logic becomes too complex to read in one line.
* **Context Managers:** Use the `with` statement for resource management (files, network connections, database sessions) to ensure proper closing.
* **Don't Reinvent the Wheel:** Use the Python Standard Library (e.g., `pathlib` for paths, `itertools` for efficient looping, `collections` for specialized data types).

## 6. Error Handling
* **Be Specific:** Never use a bare `except:`. Always catch specific exceptions (e.g., `ValueError`, `KeyError`).
* **Fail Fast:** Let errors happen early rather than masking them with `try-except` blocks that hide the root cause.

## 7. Tooling & Environment
* **Formatting:** Use automated tools like `black` or `ruff` to enforce style consistently.
* **Linting:** Use `pylint` or `flake8` to identify potential logic errors or style violations.
* **Dependencies:** Always define dependencies in a `requirements.txt` or `pyproject.toml` file.

## 8. Testing
* **Unit Tests:** Write tests for individual components using `pytest`.
* **Small Functions:** Keep functions small (Single Responsibility Principle) to make them easier to test and reuse.
