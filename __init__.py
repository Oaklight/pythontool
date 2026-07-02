"""PythonTool -- Python code execution with subprocess isolation.

Re-export facade.  When this repo is mounted as a git submodule (e.g. at
``_vendor/pythontool/``), the directory is importable as a Python package::

    from _vendor.pythontool import PythonTool
"""

from .pythontool import (
    MAX_OUTPUT_BYTES,
    PythonTool,
    __version__,
    truncate,
)

__all__ = [
    "MAX_OUTPUT_BYTES",
    "PythonTool",
    "__version__",
    "truncate",
]
