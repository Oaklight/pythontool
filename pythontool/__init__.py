"""pythontool — Python code execution with subprocess isolation.

Provides a ``PythonRuntime`` protocol for pluggable execution engines
and a default ``SubprocessRuntime`` that runs code in a separate process.

Quick start::

    from pythontool import PythonTool

    result = PythonTool.execute("print(1 + 2)")
    print(result["stdout"])  # "3\\n"

For programmatic use with custom runtimes::

    from pythontool import SubprocessRuntime, CodeResult

    runtime = SubprocessRuntime()
    result: CodeResult = runtime.execute("print('hello')", timeout=10)
"""

from ._runtime import (
    MAX_OUTPUT_BYTES,
    PythonRuntime,
    PythonTool,
    SubprocessRuntime,
    truncate,
)
from ._types import CodeResult
from ._validator import ALLOWED_IMPORTS, validate_code

__version__ = "0.2.0"

__all__ = [
    "ALLOWED_IMPORTS",
    "CodeResult",
    "MAX_OUTPUT_BYTES",
    "PythonRuntime",
    "PythonTool",
    "SubprocessRuntime",
    "__version__",
    "truncate",
    "validate_code",
]
