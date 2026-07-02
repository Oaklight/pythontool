"""Unit tests for pythontool module."""

import pytest

from pythontool import (
    CodeResult,
    PythonRuntime,
    PythonTool,
    SubprocessRuntime,
    validate_code,
)

# ---------------------------------------------------------------------------
# CodeResult
# ---------------------------------------------------------------------------


class TestCodeResult:
    def test_defaults(self):
        r = CodeResult()
        assert r.stdout == ""
        assert r.stderr == ""
        assert r.return_code == 0
        assert r.timed_out is False
        assert r.error is None

    def test_frozen(self):
        r = CodeResult()
        with pytest.raises(AttributeError):
            r.stdout = "mutate"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# PythonRuntime protocol
# ---------------------------------------------------------------------------


class TestPythonRuntimeProtocol:
    def test_subprocess_satisfies_protocol(self):
        assert isinstance(SubprocessRuntime(), PythonRuntime)

    def test_custom_runtime_satisfies_protocol(self):
        class MockRuntime:
            def execute(self, code, *, namespace=None, timeout=None):
                return CodeResult(stdout="mock")

        assert isinstance(MockRuntime(), PythonRuntime)


# ---------------------------------------------------------------------------
# SubprocessRuntime
# ---------------------------------------------------------------------------


class TestSubprocessRuntime:
    def setup_method(self):
        self.runtime = SubprocessRuntime()

    def test_print(self):
        result = self.runtime.execute("print('hello')")
        assert result.stdout.strip() == "hello"
        assert result.return_code == 0
        assert result.timed_out is False

    def test_multiline(self):
        result = self.runtime.execute("x = 10\ny = 20\nprint(x + y)")
        assert result.stdout.strip() == "30"

    def test_allowed_import(self):
        result = self.runtime.execute("import json; print(json.dumps({'a': 1}))")
        assert result.return_code == 0
        assert '"a": 1' in result.stdout

    def test_runtime_error(self):
        result = self.runtime.execute("1 / 0")
        assert result.return_code != 0
        assert "ZeroDivisionError" in result.stderr

    def test_timeout(self):
        result = self.runtime.execute("import time; time.sleep(10)", timeout=1)
        assert result.timed_out is True
        assert result.return_code == -1

    def test_namespace_stubs(self):
        """Namespace callables injected as stubs for discovery."""

        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        result = self.runtime.execute("print('add' in dir())", namespace={"add": add})
        assert result.stdout.strip() == "True"

    def test_namespace_stub_not_callable(self):
        """Stub raises NotImplementedError when called."""

        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        result = self.runtime.execute(
            "try:\n    add(a=1, b=2)\nexcept NotImplementedError:\n    print('blocked')",
            namespace={"add": add},
        )
        assert result.stdout.strip() == "blocked"

    def test_validation_disabled(self):
        """Validation can be disabled for trusted code."""
        runtime = SubprocessRuntime(validate=False)
        # This would normally be blocked
        result = runtime.execute("import os; print(os.getpid())")
        assert result.return_code == 0

    def test_empty_code(self):
        result = self.runtime.execute("")
        assert result.return_code == 0

    def test_function_definition(self):
        code = (
            "def fib(n):\n"
            "    a, b = 0, 1\n"
            "    for _ in range(n):\n"
            "        a, b = b, a+b\n"
            "    return a\n"
            "print(fib(10))"
        )
        result = self.runtime.execute(code)
        assert result.stdout.strip() == "55"


# ---------------------------------------------------------------------------
# PythonTool (static convenience API)
# ---------------------------------------------------------------------------


class TestPythonTool:
    def test_execute(self):
        result = PythonTool.execute("print(1 + 2)")
        assert result["stdout"].strip() == "3"
        assert result["exit_code"] == 0
        assert result["timed_out"] is False

    def test_return_dict_keys(self):
        result = PythonTool.execute("print('test')")
        assert set(result.keys()) == {"stdout", "stderr", "exit_code", "timed_out"}

    def test_rejects_dangerous(self):
        with pytest.raises(ValueError):
            PythonTool.execute("import os\nos.system('ls')")


# ---------------------------------------------------------------------------
# AST validation
# ---------------------------------------------------------------------------


class TestSafeCode:
    @pytest.mark.parametrize(
        "code",
        [
            "print(1 + 2)",
            "import math; print(math.sqrt(16))",
            "import json; print(json.dumps([1, 2]))",
            "import re; print(re.match(r'\\d+', '123').group())",
            "import datetime; print(datetime.date.today())",
            "import collections; c = collections.Counter('hello'); print(c)",
            "x = [i**2 for i in range(10)]; print(x)",
            "from decimal import Decimal; print(Decimal('0.1') + Decimal('0.2'))",
            # Variable names containing blocked words are fine
            "open_file_count = 5; print(open_file_count)",
            # Blocked words in strings are fine
            "x = 'import os; os.system(rm -rf /)'; print(len(x))",
            # Blocked words in comments are fine
            "# open('/etc/passwd')\nprint('safe')",
        ],
    )
    def test_safe_code_passes(self, code):
        validate_code(code)


class TestDangerousCode:
    @pytest.mark.parametrize(
        "code,reason_fragment",
        [
            ("open('/etc/passwd')", "Blocked built-in call: open"),
            ("exec('print(1)')", "Blocked built-in call: exec"),
            ("eval('1+1')", "Blocked built-in call: eval"),
            ("__import__('os')", "Blocked built-in call: __import__"),
            ("import os\nos.system('ls')", "Blocked"),
            ("import os\nos.environ['KEY']", "Blocked"),
            ("import os", "Import not allowed: 'os'"),
            ("import sys", "Import not allowed: 'sys'"),
            ("from os import path", "Import not allowed: 'os'"),
            ("import subprocess", "Import not allowed: 'subprocess'"),
            ("import socket", "Import not allowed: 'socket'"),
            ("import ctypes", "Import not allowed: 'ctypes'"),
            ("import pickle", "Import not allowed: 'pickle'"),
        ],
    )
    def test_dangerous_code_blocked(self, code, reason_fragment):
        with pytest.raises(ValueError, match=reason_fragment):
            validate_code(code)


class TestASTBypassResistance:
    def test_dangerous_in_string_literal_ok(self):
        validate_code("x = 'open(\"/etc/passwd\")'\nprint(x)")

    def test_dangerous_in_comment_ok(self):
        validate_code("# import os; os.system('rm -rf /')\nprint('safe')")

    def test_variable_name_not_false_positive(self):
        validate_code("open_count = 5\neval_mode = True\nprint(open_count)")

    def test_multiple_violations_all_reported(self):
        with pytest.raises(ValueError) as exc_info:
            validate_code("import os\nimport subprocess\nopen('x')")
        msg = str(exc_info.value)
        assert "os" in msg
        assert "subprocess" in msg
        assert "open" in msg


# ---------------------------------------------------------------------------
# Isolation
# ---------------------------------------------------------------------------


class TestIsolation:
    def test_infinite_loop_killed(self):
        result = PythonTool.execute("while True: pass", timeout=1)
        assert result["timed_out"] is True

    def test_large_output_truncated(self):
        result = PythonTool.execute("print('x' * 500_000)", timeout=5)
        assert result["exit_code"] == 0
        assert "[output truncated]" in result["stdout"]
