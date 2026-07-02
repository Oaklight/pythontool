# pythontool

Python code execution with subprocess isolation. Zero external dependencies.

## What it does

`PythonTool.execute()` runs Python code in a separate process via `subprocess.run()`:

- **Subprocess isolation** — crashes, infinite loops, and OOM in executed code cannot affect the calling process
- **Output truncation** — stdout/stderr capped at 64 KB
- **Timeout** — configurable wall-clock timeout with clean kill
- **Zero dependencies** — only Python stdlib

## Usage

### Direct import

```python
from pythontool import PythonTool

result = PythonTool.execute("print(1 + 2)")
print(result["stdout"])  # "3\n"
# result = {"stdout": "3\n", "stderr": "", "exit_code": 0, "timed_out": False}
```

### As a git submodule

```bash
git submodule add https://github.com/Oaklight/pythontool.git _vendor/pythontool
```

```python
from _vendor.pythontool import PythonTool

result = PythonTool.execute("""
import json
data = {"answer": 42}
print(json.dumps(data))
""", timeout=10)
```

### Error handling

```python
# Syntax errors
result = PythonTool.execute("def")
# exit_code != 0, stderr contains "SyntaxError"

# Runtime errors
result = PythonTool.execute("1 / 0")
# exit_code != 0, stderr contains "ZeroDivisionError"

# Timeout
result = PythonTool.execute("while True: pass", timeout=1)
# timed_out == True, exit_code == -1
```

## API

### `PythonTool.execute(code, timeout=30) -> dict`

Execute Python code in a subprocess.

- **code** (`str`): Python source code.
- **timeout** (`int`): Max seconds before kill. Default 30.

Returns `dict` with keys: `stdout`, `stderr`, `exit_code`, `timed_out`.

### `truncate(text, max_bytes=65536) -> str`

Truncate text to at most `max_bytes` UTF-8 bytes.

## Isolation guarantees

| Concern | Behavior |
|---------|----------|
| `while True: pass` | Killed on timeout |
| `ctypes.string_at(0)` (segfault) | Subprocess dies, caller survives |
| `[0] * 10**9` (OOM) | OOM kills subprocess only |
| `import os; os.system(...)` | Runs in subprocess, not caller |

## License

MIT
