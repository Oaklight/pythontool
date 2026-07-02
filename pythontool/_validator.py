"""AST-based code validation.

Walks the AST to detect dangerous constructs before execution.
Unlike regex, this is immune to string-concatenation tricks,
patterns in comments or string literals, and variable name
false positives.
"""

from __future__ import annotations

import ast

# Allowed import modules (safe for computation).
ALLOWED_IMPORTS: frozenset[str] = frozenset(
    {
        "math",
        "cmath",
        "decimal",
        "fractions",
        "statistics",
        "random",
        "string",
        "re",
        "json",
        "csv",
        "datetime",
        "time",
        "calendar",
        "collections",
        "itertools",
        "functools",
        "operator",
        "copy",
        "pprint",
        "textwrap",
        "unicodedata",
        "enum",
        "dataclasses",
        "typing",
        "types",
        "abc",
        "io",
        "base64",
        "hashlib",
        "hmac",
        "struct",
        "array",
        "bisect",
        "heapq",
        "numbers",
    }
)

# Built-in function names that are blocked.
_BLOCKED_BUILTINS: frozenset[str] = frozenset(
    {
        "open",
        "exec",
        "eval",
        "compile",
        "__import__",
        "breakpoint",
        "exit",
        "quit",
    }
)

# Attribute access patterns that are blocked.
# Keyed by object name -> set of blocked attributes.
_BLOCKED_ATTRIBUTES: dict[str, frozenset[str]] = {
    "os": frozenset(
        {
            "system",
            "popen",
            "exec",
            "execl",
            "execle",
            "execlp",
            "execlpe",
            "execv",
            "execve",
            "execvp",
            "execvpe",
            "spawn",
            "spawnl",
            "spawnle",
            "spawnlp",
            "spawnlpe",
            "spawnv",
            "spawnve",
            "spawnvp",
            "spawnvpe",
            "kill",
            "killpg",
            "environ",
            "getenv",
            "putenv",
            "unsetenv",
        }
    ),
}


class _CodeValidator(ast.NodeVisitor):
    """AST visitor that collects dangerous constructs."""

    def __init__(self) -> None:
        self.errors: list[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            module = alias.name.split(".")[0]
            if module not in ALLOWED_IMPORTS:
                self.errors.append(f"Import not allowed: {module!r} (line {node.lineno})")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            module = node.module.split(".")[0]
            if module not in ALLOWED_IMPORTS:
                self.errors.append(f"Import not allowed: {module!r} (line {node.lineno})")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        # Direct calls: open(), eval(), __import__()
        if isinstance(node.func, ast.Name) and node.func.id in _BLOCKED_BUILTINS:
            self.errors.append(f"Blocked built-in call: {node.func.id}() (line {node.lineno})")
        # Attribute calls: os.system(), os.popen()
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            obj = node.func.value.id
            attr = node.func.attr
            blocked = _BLOCKED_ATTRIBUTES.get(obj, frozenset())
            if attr in blocked:
                self.errors.append(f"Blocked call: {obj}.{attr}() (line {node.lineno})")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        # Attribute access (not just calls): os.environ["X"]
        if isinstance(node.value, ast.Name):
            obj = node.value.id
            attr = node.attr
            blocked = _BLOCKED_ATTRIBUTES.get(obj, frozenset())
            if attr in blocked:
                self.errors.append(f"Blocked attribute access: {obj}.{attr} (line {node.lineno})")
        self.generic_visit(node)


def validate_code(code: str) -> None:
    """Validate Python code via AST analysis.

    Parses the code into an AST and walks it to detect dangerous
    constructs.  Unlike regex-based checking, this is immune to:

    - String concatenation tricks
    - Dangerous patterns in comments or string literals
    - False positives from variable names

    Args:
        code: Python source code string.

    Raises:
        ValueError: With a description of why the code was rejected.
        SyntaxError: If the code cannot be parsed.
    """
    tree = ast.parse(code)
    validator = _CodeValidator()
    validator.visit(tree)
    if validator.errors:
        raise ValueError(
            "Dangerous code blocked:\n" + "\n".join(f"  - {e}" for e in validator.errors)
        )
