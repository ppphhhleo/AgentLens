```markdown
# AgentLens Development Patterns

> Auto-generated skill from repository analysis

## Overview
This skill teaches you how to contribute to the AgentLens Python codebase by following its established conventions for file organization, code style, imports/exports, and testing. You'll learn how to structure new modules, write code consistent with the repository's style, and understand the current testing patterns.

## Coding Conventions

### File Naming
- Use **snake_case** for all file and module names.
  - Example: `agent_utils.py`, `data_loader.py`

### Import Style
- Use **relative imports** within the package.
  - Example:
    ```python
    from .utils import parse_config
    from .models.agent import Agent
    ```

### Export Style
- Use **named exports**; explicitly define what is exported from each module.
  - Example:
    ```python
    __all__ = ['Agent', 'parse_config']
    ```

### Commit Messages
- Freeform style, no strict prefixes.
- Average length: ~69 characters.
  - Example:  
    ```
    Add support for new agent configuration options
    ```

## Workflows

### Adding a New Module
**Trigger:** When you need to introduce new functionality.
**Command:** `/add-module`

1. Create a new Python file using snake_case (e.g., `my_feature.py`).
2. Use relative imports to reference other modules.
3. Define your exports using `__all__`.
4. Write clear, concise functions and classes.
5. Add tests in a corresponding `*.test.*` file.

#### Example
```python
# my_feature.py
__all__ = ['my_function']

def my_function():
    pass

# In another module
from .my_feature import my_function
```

### Writing Tests
**Trigger:** When you add or modify code.
**Command:** `/write-test`

1. Create a test file with `.test.` in its name (e.g., `my_feature.test.py`).
2. Write test functions or classes for your code.
3. Use the project's preferred (currently unknown) test framework.

#### Example
```python
# my_feature.test.py
def test_my_function():
    assert my_function() is None
```

## Testing Patterns

- Test files are named with `*.test.*` (e.g., `module.test.py`).
- The specific testing framework is not detected; use standard Python testing patterns (e.g., `assert`, `unittest`, or `pytest` style).
- Place tests alongside or near the modules they cover.

## Commands
| Command       | Purpose                                   |
|---------------|-------------------------------------------|
| /add-module   | Scaffold a new module with conventions    |
| /write-test   | Create a test file for your module        |
```
