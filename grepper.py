#!/usr/bin/env python3.8

from __future__ import annotations

import argparse
import functools
import inspect
import re
import sys
from datetime import datetime
from typing import Pattern, Match as ReMatch, AnyStr, Set, Type


# `_ObjectProxy`, `_BoundFunctionWrapper`, `_FunctionWrapper` and `_decorator`
# are taken from an excellent series of blog posts on decorators.
# See https://github.com/openstack/deb-python-wrapt/tree/master/blog#decorators-2014


class _ObjectProxy:
    def __init__(self, wrapped):
        self.wrapped = wrapped
        try:
            self.__name__ = wrapped.__name__
        except AttributeError:
            pass

    @property
    def __class__(self):
        return self.wrapped.__class__

    def __getattr__(self, item):
        return getattr(self.wrapped, item)


class _BoundFunctionWrapper(_ObjectProxy):
    def __init__(self, wrapped, instance, wrapper, binding, parent):
        super().__init__(wrapped)
        self.instance = instance
        self.wrapper = wrapper
        self.binding = binding
        self.parent = parent

    def __call__(self, *args, **kwargs):
        if self.binding == "function":
            if self.instance is None:
                instance, *args = args
                wrapped = functools.partial(self.wrapped, instance)
                return self.wrapper(wrapped, instance, args, kwargs)
            else:
                return self.wrapper(self.wrapped, self.instance, args, kwargs)
        else:
            instance = getattr(self.wrapped, "__self__", None)
            return self.wrapper(self.wrapped, instance, args, kwargs)

    def __get__(self, instance, owner):
        if self.instance is None and self.binding == "function":
            descriptor = self.parent.wrapped.__get__(instance, owner)
            return _BoundFunctionWrapper(
                descriptor, instance, self.wrapper, self.binding, self.parent
            )
        return self


class _FunctionWrapper(_ObjectProxy):
    def __init__(self, wrapped, wrapper):
        super().__init__(wrapped)
        self.wrapper = wrapper
        if isinstance(wrapped, classmethod):
            self.binding = "classmethod"
        elif isinstance(wrapped, staticmethod):
            self.binding = "staticmethod"
        else:
            self.binding = "function"

    def __get__(self, instance, owner):
        wrapped = self.wrapped.__get__(instance, owner)
        return _BoundFunctionWrapper(
            wrapped, instance, self.wrapper, self.binding, self
        )

    def __call__(self, *args, **kwargs):
        return self.wrapper(self.wrapped, None, args, kwargs)


def _decorator(wrapper):
    @functools.wraps(wrapper)
    def __decorator(wrapped):
        return _FunctionWrapper(wrapped, wrapper)

    return __decorator


class CodeTrace:
    file = sys.stderr

    @classmethod
    def trace(cls, wrapped=None, *, skip=False, quiet=False):
        if wrapped is None:
            return functools.partial(cls.trace, skip=skip, quiet=quiet)

        @_decorator
        def _trace(wrapped, instance, args, kwargs):
            if skip:
                return wrapped(*args, **kwargs)

            cls._print_call_arguments(instance, wrapped, args, kwargs, quiet)
            result = wrapped(*args, **kwargs)
            cls._print_call_result(instance, wrapped, result, quiet)

            return result

        return _trace(wrapped)

    @classmethod
    def _print_call_arguments(cls, instance, fn, args, kwargs, quiet):
        signature = "" if quiet else f"({cls._signature(args, kwargs)})"
        print(f"{cls._prefix(instance, fn, 'ENTER')}{signature}", file=cls.file)

    @classmethod
    def _print_call_result(cls, instance, fn, result, quiet):
        result = "" if quiet else f"() => {result!r}"
        print(f"{cls._prefix(instance, fn, 'EXIT')}{result}", file=cls.file)

    @classmethod
    def _prefix(cls, instance, fn, action):
        return f"{cls._timestamp()} *** {action} {cls._format_call(fn, instance)}"

    @staticmethod
    def _format_call(function, instance):
        if instance is None:
            # function or staticmethod is called
            prefix = "[fn] "
        else:
            if inspect.isclass(instance):
                # classmethod is called
                prefix = f"[cm] {instance.__name__}."
            else:
                # instance method is called
                prefix = f"[im] {type(instance).__name__}."
        name = f"{prefix}{function.__name__}"
        return name

    @staticmethod
    def _signature(args, kwargs):
        positional = (repr(arg) for arg in args)
        keyword = (f"{k}={v!r}" for k, v in kwargs.items())
        return ", ".join([*positional, *keyword])

    @staticmethod
    def _timestamp():
        return datetime.now().isoformat(timespec="microseconds")


_TOKEN_GROUP_PREFIX = "token_"
_TOKEN_CAPTURE_RE = r"%\\{(?P<index>\d+)(?P<modifier>G|S(\d+))?\\}"


class Match(_ObjectProxy):
    """Wrapper around a `re.Match`

    Provides additional method `token` which can be used to retrieve
    a match text by original token index.

    Also provides a `line` property to access a full matched line.
    """

    def __init__(self, match: ReMatch, pattern: str = None):
        super().__init__(match)
        self.pattern = pattern

    def token(self, index: int):
        """Get matched text by token index"""
        return self.wrapped.group(f"{_TOKEN_GROUP_PREFIX}{index}")

    @property
    def line(self) -> AnyStr:
        return self.wrapped.string


class Grepper:
    """This class is used to match lines according to provided patterns.

    A pattern is a text string delimited with token capture sequences.
    For example, "foo %{0} is a %{1}" would match following lines:

    - "foo blah is a bar"
    - "foo blah is a very big boat"

    But it would not match:

    - "foo blah is bar"
    - "foo blah"
    - "foo blah is"

    Two modifiers can be applied to a token capture sequence.

    - a whitespace modifier - %{0S1} - limits the number of spaces within a match
    - a greedy modifier - %{0G} - matches a much text as possible

    One or more patterns is required.

    Usage example:
    >>> grepper = Grepper("foo %{0} is a %{1}")
    >>> match = grepper.match_line("foo blah is a very big boat")
    >>> assert bool(match)

    Individual token can be retrieved from a match by index:
    >>> assert match.token(0) == "blah"
    >>> assert match.token(1) == "vary big boat"

    As well as a full matched line:
    >>> assert match.line == "foo blah is a very big boat"
    """

    # The class is used for line matching
    match_class: Type[Match] = Match

    @CodeTrace.trace
    def __init__(self, *patterns: str):
        if not patterns:
            raise ValueError("One or more patterns is required")
        self.patterns = tuple(patterns)

        # escape provided patterns for safe regex construction
        escaped_patterns = (re.escape(pattern) for pattern in self.patterns)
        self.regexes = tuple(
            self.map_pattern_to_re(pattern) for pattern in escaped_patterns
        )

    @CodeTrace.trace
    @classmethod
    def map_pattern_to_re(cls, pattern: str) -> Pattern:
        """Maps a text pattern to a regular expression

        :param pattern: an escaped text pattern
        """

        # keep track of indices in case there are duplicates
        seen_indices = set()
        token_mapper = functools.partial(cls._map_token_to_re, indices=seen_indices)
        regex = re.sub(_TOKEN_CAPTURE_RE, token_mapper, pattern)
        return re.compile(f"^{regex}$", flags=re.UNICODE)

    @CodeTrace.trace
    @classmethod
    def _map_token_to_re(cls, token_match: ReMatch, indices: Set[AnyStr]) -> AnyStr:
        index, modifier = token_match.group("index", "modifier")

        if index in indices:
            cls._raise_on_duplicate_token_index(token_match)
        else:
            indices.add(index)

        regex = f"(?P<{_TOKEN_GROUP_PREFIX}{index}>%s)"
        if not modifier:
            return regex % ".*?"
        if modifier == "G":
            return regex % ".*"
        elif modifier.startswith("S"):
            total_spaces = modifier[1:]
            return regex % fr"(?:\S*\s\S*){{{total_spaces}}}\S*"

    @CodeTrace.trace
    @classmethod
    def _raise_on_duplicate_token_index(cls, token_match):
        unescaped_token = cls._unescape(token_match.group(0))
        unescaped_pattern = cls._unescape(token_match.string)
        raise ValueError(
            f"Duplicate token index {unescaped_token} in {unescaped_pattern!r}"
        )

    @CodeTrace.trace
    @staticmethod
    def _unescape(string):
        return re.sub(r"\\(.)", r"\1", string)

    @CodeTrace.trace
    def match_line(self, line: str) -> Grepper.match_class:
        """Match a line against provided patterns

        Returns a first match.
        """
        for i, regex in enumerate(self.regexes):
            if match := regex.match(line):
                return self.match_class(match, self.patterns[i])


@CodeTrace.trace
def _create_parser():
    parser = argparse.ArgumentParser(
        description="Filter input lines according to provided pattern[s]"
    )
    parser.add_argument("patterns", nargs="+", help="pattern specifications")
    parser.add_argument(
        "-i", "--in-file", type=argparse.FileType("r"), default=sys.stdin
    )
    parser.add_argument(
        "-o", "--out-file", type=argparse.FileType("w"), default=sys.stdout
    )
    parser.add_argument(
        "-t", "--trace-file", type=argparse.FileType("w"), default=sys.stderr
    )
    return parser


@CodeTrace.trace
def main(*patterns: str):
    parser = _create_parser()
    args = parser.parse_args(list(patterns) or None)

    CodeTrace.file = args.trace_file

    try:
        grepper = Grepper(*args.patterns)
    except ValueError as e:
        raise SystemExit(e) from e

    try:
        for line in args.in_file:
            line = line.rstrip("\n")
            if match := grepper.match_line(line):
                print(match.line, file=args.out_file)
    except KeyboardInterrupt:
        raise SystemExit(0)


if __name__ == "__main__":
    main()
