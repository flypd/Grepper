# Grepper

Grepper is a command-line utility that translates a pattern
specification provided as a command-line argument into
a regular expression, processes lines of input text received
from `stdin` using that regular expression to quantify matches,
and finally writes each matching input line to `stdout`.

**NOTE: requires ^python3.8**

## Installation

```
>>> pip install git+https://github.com/flypd/Grepper
```

## Usage example
```
>>> cat input.txt
foo blah is a bar
foo blah is a very big boat
foo blah is bar
foo blah
foo blah is
>>> cat input.txt | grepper "foo %{0} is a %{1}" 2>/dev/null
foo blah is a bar
foo blah is a very big boat
```

One or more patterns are treated as a logical OR when matching line

```
>>> cat input2.txt
foo blah is a bar
foo bar baz
foo blah is a very big boat
foo blah is bar
foo blah
foo blah is
>>> cat input2.txt | grepper "foo %{0} is a %{1}" "foo %{0} baz" 2>/dev/null
foo blah is a bar
foo bar baz
foo blah is a very big boat
```


## Tests

```
>>> pytest tests/
```
