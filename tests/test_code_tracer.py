import sys

import pytest

from grepper import CodeTrace


@CodeTrace.trace
def a_function(arg):
    pass


class AClass:
    @CodeTrace.trace
    def a_method(self, arg):
        pass

    @CodeTrace.trace
    @classmethod
    def a_classmethod(cls, arg):
        pass

    @CodeTrace.trace
    @staticmethod
    def a_staticmethod(arg):
        pass


@pytest.mark.parametrize(
    "decorated, expected_prefix",
    [
        (a_function, "[fn] a_function"),
        (AClass().a_method, "[im] AClass.a_method"),
        (AClass().a_classmethod, "[cm] AClass.a_classmethod"),
        (AClass.a_staticmethod, "[fn] a_staticmethod"),
        (AClass().a_staticmethod, "[fn] a_staticmethod"),
    ],
)
def test_trace_decorator(decorated, expected_prefix, capsys, monkeypatch):
    monkeypatch.setattr("grepper.CodeTrace.file", sys.stderr)

    decorated("some_argument")
    err = capsys.readouterr().err

    lines = err.splitlines()
    assert len(lines) == 2
    enter_line, exit_line = lines
    assert "ENTER" in enter_line
    assert "EXIT" in exit_line

    assert expected_prefix in enter_line
    assert expected_prefix in exit_line

    assert "some_argument" in enter_line
