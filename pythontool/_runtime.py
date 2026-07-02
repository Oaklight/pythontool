"""PythonRuntime protocol and default SubprocessRuntime implementation.

A ``PythonRuntime`` executes Python code strings with an optional
namespace of callable functions.  The protocol is intentionally simple:
``execute(code, namespace, timeout) -> CodeResult``.

The default ``SubprocessRuntime`` runs code in a subprocess for crash
isolation.  Namespace callables are **not** available inside the
subprocess (they live in the parent process).  Full namespace support
with IPC will be added in a future ``IpcSubprocessRuntime``.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable

from ._types import CodeResult
from ._validator import validate_code

# Maximum bytes kept for stdout / stderr to prevent memory exhaustion.
MAX_OUTPUT_BYTES = 65_536  # 64 KB


def truncate(text: str, max_bytes: int = MAX_OUTPUT_BYTES) -> str:
    """Truncate *text* to at most *max_bytes* UTF-8 bytes.

    If truncation occurs, a marker is appended so the caller knows the
    output was clipped.

    Args:
        text: The string to truncate.
        max_bytes: Maximum number of UTF-8 bytes allowed.

    Returns:
        The (possibly truncated) string.
    """
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= max_bytes:
        return text
    truncated = encoded[:max_bytes].decode("utf-8", errors="ignore")
    return truncated + "\n... [output truncated]"


@runtime_checkable
class PythonRuntime(Protocol):
    """Protocol for Python code execution engines.

    Implementations decide the isolation strategy (in-process,
    subprocess, container, etc.) and how namespace callables are
    made available to the executed code.

    The ``namespace`` is a plain ``dict[str, Callable]`` — this
    package has no knowledge of ``ToolProjection`` or ``ToolRegistry``.
    Callers are responsible for converting their tool abstractions
    into bare callables before passing them here.
    """

    def execute(
        self,
        code: str,
        *,
        namespace: dict[str, Callable[..., Any]] | None = None,
        timeout: float | None = None,
    ) -> CodeResult:
        """Execute Python *code* and return structured output.

        Args:
            code: Python source code to execute.
            namespace: Mapping of name -> callable to inject into the
                execution namespace.  The code can call these directly.
                ``None`` means no external callables.
            timeout: Maximum wall-clock seconds.  ``None`` means no limit.

        Returns:
            A :class:`CodeResult` with captured stdout, stderr, and
            error information.
        """
        ...


class SubprocessRuntime:
    """Execute Python code in a subprocess for crash isolation.

    The code is validated via AST analysis, then run in a fresh
    Python process via ``subprocess.run()``.  Crashes, infinite loops,
    and resource exhaustion cannot affect the calling process.

    Namespace callables are serialized as a JSON ``dict[str, str]``
    mapping name -> docstring, and injected as stub functions that
    raise ``NotImplementedError``.  This allows the LLM-generated code
    to discover available functions via ``help()`` but not actually
    call them.  Full IPC-based calling will be added in a future
    ``IpcSubprocessRuntime``.

    Note:
        For full namespace support where code can *call* the provided
        callables across the process boundary, use a future
        ``IpcSubprocessRuntime`` (requires bidirectional IPC).
    """

    def __init__(self, *, validate: bool = True) -> None:
        """Initialize the runtime.

        Args:
            validate: Whether to run AST validation before execution.
                Set to ``False`` only for trusted code.
        """
        self._validate = validate

    def execute(
        self,
        code: str,
        *,
        namespace: dict[str, Callable[..., Any]] | None = None,
        timeout: float | None = None,
    ) -> CodeResult:
        """Execute Python code in a subprocess.

        Args:
            code: Python source code to execute.
            namespace: Mapping of name -> callable.  In subprocess mode,
                callables are injected as stubs (docstring only).
            timeout: Maximum wall-clock seconds before kill.

        Returns:
            A :class:`CodeResult` with captured output.

        Raises:
            ValueError: If validation is enabled and the code contains
                dangerous constructs.
            SyntaxError: If the code cannot be parsed.
        """
        if self._validate:
            validate_code(code)

        # Build the execution script
        script = self._build_script(code, namespace)

        effective_timeout = timeout if timeout is not None else None
        try:
            result = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True,
                text=True,
                timeout=effective_timeout,
            )
            return CodeResult(
                stdout=truncate(result.stdout),
                stderr=truncate(result.stderr),
                return_code=result.returncode,
                timed_out=False,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout
            stderr = exc.stderr
            return CodeResult(
                stdout=truncate(stdout if isinstance(stdout, str) else ""),
                stderr=truncate(stderr if isinstance(stderr, str) else ""),
                return_code=-1,
                timed_out=True,
            )

    def _build_script(
        self,
        code: str,
        namespace: dict[str, Callable[..., Any]] | None,
    ) -> str:
        """Build the full script to run in the subprocess.

        If a namespace is provided, stub functions are prepended so the
        code can reference them (for discovery / help()).
        """
        if not namespace:
            return code

        # Build stub definitions from namespace callables
        stubs: list[str] = []
        for name, fn in namespace.items():
            doc = getattr(fn, "__doc__", None) or f"Stub for {name}"
            # Escape for safe embedding
            doc_escaped = json.dumps(doc)
            stubs.append(
                f"def {name}(**kwargs):\n"
                f"    {doc_escaped}\n"
                f"    raise NotImplementedError("
                f"'Cannot call {name}() in subprocess mode')\n"
            )

        preamble = "\n".join(stubs)
        return preamble + "\n" + code


class PythonTool:
    """Convenience wrapper — static API compatible with ``BashTool``.

    Uses :class:`SubprocessRuntime` internally.

    Usage::

        from pythontool import PythonTool

        result = PythonTool.execute("print(1 + 2)")
        print(result["stdout"])  # "3\\n"
    """

    _runtime = SubprocessRuntime()

    @staticmethod
    def execute(
        code: str,
        timeout: int = 30,
    ) -> dict[str, Any]:
        """Execute Python code in a subprocess and return its output.

        Args:
            code: Python source code to execute.
            timeout: Maximum wall-clock seconds before kill.  Defaults to 30.

        Returns:
            A dict with keys ``stdout``, ``stderr``, ``exit_code``,
            ``timed_out``.

        Raises:
            ValueError: If the code contains dangerous constructs.
            SyntaxError: If the code cannot be parsed.
        """
        result = PythonTool._runtime.execute(code, timeout=timeout)
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.return_code,
            "timed_out": result.timed_out,
        }
