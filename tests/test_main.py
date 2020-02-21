import io
import sys

import pytest

from grepper import main

INPUT = """
foo blah is a bar
foo blah is bar
foo blah
foo blah is
foo blah is a very big boat
"""

EXPECTED_OUTPUT = """\
foo blah is a bar
foo blah is a very big boat
"""

EXPECTED_OUTPUT_MULTIPLE_PATTERNS = """\
foo blah is a bar
foo blah
foo blah is a very big boat
"""

PATTERN = "foo %{0} is a %{1}"
MULTIPLE_PATTERNS = ("foo %{0} is a %{1}", "foo blah")


@pytest.fixture(scope="function")
def patch_out_and_err(monkeypatch, capsys):
    with capsys.disabled():
        out = io.StringIO()
        err = io.StringIO()
        monkeypatch.setattr("sys.stdout", out)
        monkeypatch.setattr("sys.stderr", err)
        yield out, err
        monkeypatch.undo()


@pytest.mark.parametrize(
    "patterns,input_,output",
    [
        ((PATTERN,), INPUT, EXPECTED_OUTPUT),
        (MULTIPLE_PATTERNS, INPUT, EXPECTED_OUTPUT_MULTIPLE_PATTERNS),
    ],
)
def test_main(patterns, input_, output, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(input_))
    monkeypatch.setattr("grepper.CodeTrace.file", sys.stderr)

    main(*patterns)

    out, _ = capsys.readouterr()
    assert out == output
