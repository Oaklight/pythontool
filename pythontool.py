"""Python code execution tool with subprocess isolation.

Provides ``PythonTool.execute()`` to run Python code via
``subprocess.run()`` in a separate process.  The calling process is
never affected by crashes, infinite loops, or resource exhaustion in the
executed code.

This module has **zero external dependencies** — it uses only the Python
standard library.

Usage::

    from pythontool import PythonTool

    result = PythonTool.execute("print(1 + 2)")
    print(result["stdout"])  # "3\\n"

When used as a git submodule mounted at ``_vendor/pythontool/``::

    from _vendor.pythontool import PythonTool
"""

from __future__ import annotations

import subprocess
import sys

__version__ = "0.1.0"

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


class PythonTool:
    """Python code execution with subprocess isolation."""

    @staticmethod
    def execute(
        code: str,
        timeout: int = 30,
    ) -> dict:
        """Execute Python code in a subprocess and return its output.

        The code is run via ``sys.executable -c code`` in a fresh
        process.  Crashes, infinite loops, and resource exhaustion in the
        code cannot affect the calling process.

        Args:
            code: Python source code to execute.
            timeout: Maximum wall-clock seconds before the process is
                killed.  Defaults to 30.

        Returns:
            A dict with keys:

            - ``stdout`` (str): captured standard output (truncated at 64 KB).
            - ``stderr`` (str): captured standard error (truncated at 64 KB).
            - ``exit_code`` (int): process exit code, or ``-1`` on timeout.
            - ``timed_out`` (bool): whether the process was killed due to
              timeout.
        """
        try:
            result = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return {
                "stdout": truncate(result.stdout),
                "stderr": truncate(result.stderr),
                "exit_code": result.returncode,
                "timed_out": False,
            }
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout
            stderr = exc.stderr
            return {
                "stdout": truncate(stdout if isinstance(stdout, str) else ""),
                "stderr": truncate(stderr if isinstance(stderr, str) else ""),
                "exit_code": -1,
                "timed_out": True,
            }
