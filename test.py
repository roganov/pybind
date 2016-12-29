from typing import Optional, Tuple

import pytest

from pybind import bind, try_unwrap_optional


def test():
    class X:
        x: int
        y: bool

    x = bind(X, {'x': 1, 'y': False})

    assert isinstance(x, X)
    assert x.x == 1
    assert x.y is False


def test_optional():
    class X:
        x: Optional[int]

    assert bind(X, {}).x is None
    assert bind(X, {'x': 1}).x == 1


def test_nested():
    class Y:
        a: int
        b: str

    class X:
        y: Y

    x = bind(X, {'y': {'a': 1, 'b': '123'}})

    assert isinstance(x.y, Y)
    assert x.y.a == 1
    assert x.y.b == '123'


def test_tuples():
    Point = Tuple[float, float, Tuple[str, int]]

    p = bind(Point, ['0', '1', ['abc', 3]])

    assert p == (0., 1., ('abc', 3))


def test_try_unwrap_optional():
    assert try_unwrap_optional(int) == (False, int)
    assert try_unwrap_optional(Optional[int]) == (True, int)
    assert try_unwrap_optional(Optional[Optional[int]]) == (True, int)
