import re

import pytest

from grepper import Grepper


@pytest.fixture(scope="function")
def regex(request):
    return re.compile(request.param)


@pytest.mark.parametrize(
    "token_capture,regex",
    [
        ("%{0}", "^(?P<token_0>.*?)$"),
        ("%{1}", "^(?P<token_1>.*?)$"),
        ("%{0S1}", r"^(?P<token_0>(?:\S*\s\S*){1}\S*)$"),
    ],
    indirect=["regex"],
)
def test_map_token_capture_to_re(token_capture, regex):
    mapped = Grepper.map_pattern_to_re(re.escape(token_capture))
    assert mapped == regex


def test_raises_when_no_patterns_provided():
    with pytest.raises(ValueError):
        Grepper()


SIMPLE_PATTERN = "foo %{0} is a %{1}"
SPACE_LIMITATION_PATTERN = "foo %{0} is a %{1S0}"
GREEDY_PATTERN = "bar %{0G} foo %{1}"


@pytest.mark.parametrize(
    "pattern,test_string,expected",
    [
        (SIMPLE_PATTERN, "foo blah is a bar", True),
        (SIMPLE_PATTERN, "foo blah is a very big boat", True),
        (SIMPLE_PATTERN, "foo blah is bar", False),
        (SIMPLE_PATTERN, "foo blah", False),
        (SIMPLE_PATTERN, "foo blah is", False),
        (SPACE_LIMITATION_PATTERN, "foo blah is a bar", True),
        (SPACE_LIMITATION_PATTERN, "foo blah is a very big boat", False),
        (SPACE_LIMITATION_PATTERN, "foo blah is bar", False),
        (SPACE_LIMITATION_PATTERN, "foo blah", False),
        (SPACE_LIMITATION_PATTERN, "foo blah is", False),
        (GREEDY_PATTERN, "bar foo bar foo bar foo bar foo", True),
    ],
)
def test_patterns(pattern, test_string, expected):
    grepper = Grepper(pattern)
    assert bool(grepper.match_line(test_string)) == expected


def test_adjacent_capture_sequences():
    grepper = Grepper("the %{0S1} %{1} ran away")
    match = grepper.match_line("the big brown fox ran away")
    assert bool(match)
    assert match.token(0) == "big brown"
    assert match.token(1) == "fox"

    assert match.re == re.compile(
        "^the\\ (?P<token_0>(?:\\S*\\s\\S*){1}\\S*)\\ (?P<token_1>.*?)\\ ran\\ away$"
    )
    assert match.pattern == "the %{0S1} %{1} ran away"


def test_raises_on_duplicate_tokens():
    with pytest.raises(ValueError):
        Grepper("foo %{0} is a %{0}")


@pytest.mark.parametrize(
    "line,expected", [("foo", True), ("baz", True), ("blah", False)]
)
def test_matches_multiple_patterns(line, expected):
    grepper = Grepper("foo", "baz")
    assert bool(grepper.match_line(line)) == expected
