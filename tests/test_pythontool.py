"""Unit tests for pythontool module."""

from pythontool import PythonTool


class TestPythonToolExecute:
    """Test cases for PythonTool.execute()."""

    def test_print(self):
        result = PythonTool.execute("print('hello')")
        assert result["stdout"].strip() == "hello"
        assert result["exit_code"] == 0
        assert result["timed_out"] is False

    def test_expression_result(self):
        result = PythonTool.execute("print(1 + 2)")
        assert result["stdout"].strip() == "3"

    def test_multiline(self):
        code = "x = 10\ny = 20\nprint(x + y)"
        result = PythonTool.execute(code)
        assert result["stdout"].strip() == "30"

    def test_import(self):
        result = PythonTool.execute("import json; print(json.dumps({'a': 1}))")
        assert result["exit_code"] == 0
        assert '"a": 1' in result["stdout"]

    def test_stderr(self):
        result = PythonTool.execute("import sys; print('err', file=sys.stderr)")
        assert "err" in result["stderr"]

    def test_syntax_error(self):
        result = PythonTool.execute("def")
        assert result["exit_code"] != 0
        assert "SyntaxError" in result["stderr"]

    def test_runtime_error(self):
        result = PythonTool.execute("1 / 0")
        assert result["exit_code"] != 0
        assert "ZeroDivisionError" in result["stderr"]

    def test_nonzero_exit_code(self):
        result = PythonTool.execute("import sys; sys.exit(42)")
        assert result["exit_code"] == 42
        assert result["timed_out"] is False

    def test_timeout(self):
        result = PythonTool.execute("import time; time.sleep(10)", timeout=1)
        assert result["timed_out"] is True
        assert result["exit_code"] == -1

    def test_return_dict_keys(self):
        result = PythonTool.execute("print('test')")
        assert set(result.keys()) == {"stdout", "stderr", "exit_code", "timed_out"}

    def test_stdout_truncation(self):
        result = PythonTool.execute("print('x' * 200_000)")
        assert result["exit_code"] == 0
        assert "[output truncated]" in result["stdout"]

    def test_empty_code(self):
        result = PythonTool.execute("")
        assert result["exit_code"] == 0
        assert result["stdout"] == ""


class TestPythonToolIsolation:
    """Verify subprocess isolation properties."""

    def test_crash_does_not_affect_caller(self):
        """Segfault-like crash in subprocess should not crash us."""
        result = PythonTool.execute("import ctypes; ctypes.string_at(0)", timeout=5)
        assert result["exit_code"] != 0
        assert result["timed_out"] is False

    def test_env_isolation(self):
        """Subprocess inherits env but runs independently."""
        result = PythonTool.execute("import os; print(os.getpid())")
        assert result["exit_code"] == 0
        import os

        assert result["stdout"].strip() != str(os.getpid())

    def test_infinite_loop_killed(self):
        result = PythonTool.execute("while True: pass", timeout=1)
        assert result["timed_out"] is True

    def test_oom_contained(self):
        """Large allocation should fail in subprocess, not here."""
        result = PythonTool.execute("[0] * (10**9)", timeout=5)
        assert result["exit_code"] != 0 or result["timed_out"]
