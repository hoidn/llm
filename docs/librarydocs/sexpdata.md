# Developer Guide for sexpdata

This guide provides information for developers who want to contribute to or use the `sexpdata` Python package.

## Overview

`sexpdata` is a simple S-expression parser/serializer for Python. It provides functionality similar to the `pickle`, `json`, or `PyYAML` modules with simple `load` and `dump` functions.

## Installation

```bash
pip install sexpdata
```

For development installation:

```bash
git clone https://github.com/jd-boyd/sexpdata.git
cd sexpdata
pip install -e .
```

## Basic Usage

```python
from sexpdata import loads, dumps

# Parse an S-expression string into Python objects
data = loads('("a" "b")')  # ['a', 'b']

# Convert Python objects to an S-expression string
sexp = dumps(['a', 'b'])  # '("a" "b")'
```

## Core Classes

### Symbol

The `Symbol` class represents symbolic atoms in S-expressions:

```python
from sexpdata import Symbol

sym = Symbol('foo')
```

Symbols are automatically created when parsing an S-expression without quotes.

### String

The `String` class is used for string literals:

```python
from sexpdata import String

str_obj = String('bar')
```

### Quoted

The `Quoted` class represents quoted S-expressions:

```python
from sexpdata import Quoted, Symbol

quoted_sym = Quoted(Symbol('baz'))  # Represents 'baz
```

### Delimiters

The base class for different types of bracketed expressions. Two built-in subclasses:

- `Parens`: For parenthesized expressions like `(a b c)`
- `Brackets`: For bracket expressions like `[a b c]`

You can extend with custom delimiter types:

```python
from sexpdata import Delimiters

class Braces(Delimiters):
    opener, closer = '{', '}'
```

## Main Functions

### loads(string, **kwargs)

Parse an S-expression string into Python objects.

Parameters:
- `string`: The S-expression string to parse
- `nil`: Symbol to interpret as an empty list (default: `'nil'`)
- `true`: Symbol to interpret as True (default: `'t'`)
- `false`: Symbol to interpret as False (default: `None`)
- `line_comment`: Character that starts a line comment (default: `';'`)

### dumps(obj, **kwargs)

Convert Python objects to an S-expression string.

Parameters:
- `obj`: The Python object to convert
- `str_as`: How to output strings, either `'symbol'` or `'string'` (default: `'string'`)
- `tuple_as`: How to output tuples, either `'list'` or `'array'` (default: `'list'`)
- `true_as`: How to output True (default: `'t'`)
- `false_as`: How to output False (default: `'()'`)
- `none_as`: How to output None (default: `'()'`)
- `pretty_print`: Whether to format output as a tree (default: `False`)
- `indent_as`: String to use for indentation (default: `'  '`)

### load(file-like, **kwargs)

Parse an S-expression from a file-like object.

### dump(obj, file-like, **kwargs)

Write an S-expression to a file-like object.

## Utility Functions

### car(obj)

Returns the first element of a list (similar to Lisp's `car`).

### cdr(obj)

Returns all elements except the first (similar to Lisp's `cdr`).

## Nil Handling and Special Values

### Nil Handling

Nil (`nil`) is a special symbol in Lisp that represents an empty list or "nothing". In `sexpdata`, nil handling is customizable:

1. **Default behavior**: By default, the symbol `'nil'` is interpreted as an empty list `[]`:
   ```python
   loads("nil")  # Returns []
   ```

2. **Custom nil symbol**: You can specify a different symbol to be interpreted as nil:
   ```python
   loads("null", nil='null')  # Returns []
   ```

3. **Disabling nil conversion**: You can disable nil conversion by setting `nil=None`:
   ```python
   loads("nil", nil=None)  # Returns Symbol('nil')
   ```

4. **Serializing empty lists**: When serializing data, empty lists are converted to the specified nil representation:
   ```python
   dumps([])  # Returns "nil" (by default)
   ```

5. **Nil vs. false**: In some Lisp dialects, nil represents both an empty list and falsehood. In `sexpdata`, these concepts are separate, but can be configured to match your desired behavior.

### Boolean Values

1. **True value**: By default, the symbol `'t'` is interpreted as `True`:
   ```python
   loads("t")  # Returns True
   dumps(True)  # Returns "t" 
   ```

2. **Custom true symbol**: You can specify a different symbol to represent `True`:
   ```python
   loads("#t", true='#t')  # Returns True
   dumps(True, true_as='#t')  # Returns "#t"
   ```

3. **False value**: By default, no symbol is automatically converted to `False` (you must specify one):
   ```python
   loads("#f", false='#f')  # Returns False
   dumps(False, false_as='#f')  # Returns "#f" (default is "()")
   ```

4. **None value**: By default, `None` is serialized as `"()"`:
   ```python
   dumps(None)  # Returns "()"
   dumps(None, none_as='null')  # Returns "null"
   ```

## Common Gotchas and Edge Cases

### 1. Nil vs. Empty List Ambiguity

Lisp dialects vary in how they treat nil and empty lists. In some dialects, they're identical, while in others they're distinct concepts. `sexpdata` by default follows the convention where `nil` is an empty list, but this can cause confusion:

```python
# These both produce empty lists in Python
loads("nil")
loads("()")

# But when serializing back, only empty lists become "nil"
dumps([])  # "nil" 
```

**Recommendation**: If working with code that needs a distinction, configure `nil=None` when parsing:

```python
loads("nil", nil=None)  # Returns Symbol('nil'), not []
loads("()")  # Will still give you []
```

### 2. String vs. Symbol Representation

Strings and symbols are distinct types in S-expressions, but Python strings don't capture this distinction:

```python
# These produce different Python objects
loads("abc")  # Symbol('abc')
loads("\"abc\"")  # 'abc' (Python string)

# When serializing standard Python strings
dumps("abc")  # "\"abc\"" (as a string)
dumps("abc", str_as='symbol')  # "abc" (as a symbol)
```

**Recommendation**: Be consistent with your use of `str_as` parameter and use the `Symbol` class explicitly when needed.

### 3. Quoted Expressions

Quoting in Lisp prevents evaluation, but Python doesn't have this concept natively:

```python
loads("'foo")  # Quoted(Symbol('foo'))
loads("'(a b)")  # Quoted([Symbol('a'), Symbol('b')])
```

When serializing, ensure you understand the difference between:
```python
dumps(Quoted(Symbol('foo')))  # "'foo"
dumps(Quoted(['a', 'b']))  # "'(\"a\" \"b\")"
```

### 4. Unicode and Character Encoding

When working with Unicode strings:

1. Python 2/3 differences: `sexpdata` handles the Python 2/3 string differences internally, but be aware of the distinction.

2. Special characters in symbols require escaping:
   ```python
   Symbol('a b')  # Contains a space, would be escaped
   tosexp(Symbol('a b'))  # "a\\ b" 
   ```

### 5. Binary Data

S-expressions don't have a native binary data type, so binary data needs conversion:
```python
# This raises an AssertionError - don't try to parse bytes directly
loads(b"(data)")  

# Convert binary data to a string representation first
loads(b"(data)".decode('utf-8'))
```

### 6. Type Conversion Edge Cases

1. Custom types: Objects without a registered handler will raise a `TypeError` when trying to serialize them.

2. Integer vs. float distinction: S-expressions generally don't distinguish between integer and float types, but `sexpdata` preserves this distinction.

3. Empty quoted expressions: `'()` is parsed as `Quoted([])`, not as a special value.

### 7. Performance Considerations

1. **Large S-expressions**: The parser loads the entire expression into memory, which can be a problem for very large expressions.

2. **Recursion depth**: Very deeply nested expressions might hit Python's recursion limit.

## Extending the Parser

You can customize how objects are converted to S-expressions by registering functions with the `@tosexp.register` decorator:

```python
from sexpdata import tosexp
from collections import namedtuple

# Create a custom class
MyClass = namedtuple('MyClass', 'value')

# Register a conversion function
@tosexp.register(MyClass)
def _(obj, **kwds):
    return f"MyClass({tosexp(obj.value, **kwds)})"
```

Alternatively, you can add a `__to_lisp_as__` method to your class:

```python
class MyCustomClass:
    def __init__(self, value):
        self.value = value
        
    def __to_lisp_as__(self):
        return {'type': 'custom', 'value': self.value}
```

## Custom Delimiters

You can extend the `Delimiters` class to support additional bracket types:

```python
class Braces(Delimiters):
    opener, closer = '{', '}'
```

After defining a custom delimiter class, the parser will recognize these delimiters automatically:

```python
# Before defining Braces, this would parse as symbols
parse('{a b c}')  # [Symbol('{a'), Symbol('b'), Symbol('c}')]

# After defining Braces
parse('{a b c}')  # Braces([Symbol('a'), Symbol('b'), Symbol('c')])
```

## Testing

Tests are written using pytest. To run the tests:

```bash
pytest
```

Or with tox to test across multiple Python versions:

```bash
tox
```

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Run tests to make sure they pass (`pytest`)
4. Commit your changes 
5. Push to the branch
6. Open a Pull Request

## Making a Release

1. Build the package: `python -m build`
2. Check the distribution: `twine check dist/*`
3. Tag the release: `git tag v1.0.x`
4. Upload to PyPI: `twine upload dist/*`

## License

`sexpdata` is licensed under the BSD 2-Clause License.
