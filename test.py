from typing import Optional, Tuple, List, NewType, NamedTuple, Union, Any

import pytest

from pybind import bind, try_unwrap_optional, is_namedtuple


class TestUserClass:
    def test(self):
        class X:
            x: int
            y: bool

        x = bind(X, {'x': 1, 'y': False})

        assert isinstance(x, X)
        assert x.x == 1
        assert x.y is False

    def test_optional(self):
        class X:
            x: Optional[int]

        assert bind(X, {}).x is None
        assert bind(X, {'x': 1}).x == 1

    def test_nested(self):
        class Y:
            a: int
            b: str

        class X:
            y: Y

        x = bind(X, {'y': {'a': 1, 'b': '123'}})

        assert isinstance(x.y, Y)
        assert x.y.a == 1
        assert x.y.b == '123'

    def test_subclass(self):
        class X:
            x: int

        class XX(X):
            xx: str

        xx = bind(XX, {'x': '1', 'xx': 'xx'})

        assert isinstance(xx, XX)
        assert xx.x == 1
        assert xx.xx == 'xx'


def test_tuples():
    Point = Tuple[float, float, Tuple[str, int]]

    p = bind(Point, ['0', '1', ['abc', 3]])

    assert p == (0., 1., ('abc', 3))


def test_tuple_with_optional():
    Point = Tuple[float, Optional[float]]

    assert bind(Point, ['1.1']) == (1.1, None)


def test_list():
    xs = bind(List[int], ['1', 2, '3'])
    assert xs == [1, 2, 3]


def test_newtype():
    UserId = NewType('UserId', int)

    class X:
        user_id: UserId

    assert bind(X, {'user_id': '1'}).user_id == 1


def test_try_unwrap_optional():
    assert try_unwrap_optional(int) == (False, int)
    assert try_unwrap_optional(Optional[int]) == (True, int)
    assert try_unwrap_optional(Optional[Optional[int]]) == (True, int)


class TestNamedTuple:

    class X(NamedTuple):
        a: int
        b: str

    class XX(X):
        c: str

    class XOpt(NamedTuple):
        a: int
        b: Optional[str]

    def test_positional(self):
        x = bind(self.X, [1, 'b'])

        assert x == self.X(a=1, b='b')

    def test_positional_with_optional(self):
        x = bind(self.XOpt, [1])
        assert x == self.XOpt(a=1, b=None)

    def test_named(self):
        x = bind(self.X, {'a': '1', 'b': 'b'})

        assert x == self.X(a=1, b='b')

    def test_named_with_optional(self):
        x = bind(self.XOpt, {'a': '1'})
        assert x == self.XOpt(a=1, b=None)

    @pytest.mark.skip
    def test_subclass(self):
        xx = bind(self.XX, {'a': '1', 'b': 'b', 'c': 'c'})

        assert xx == self.XX(a=1, b='b', c='c')


def test_union():
    U = Union[int, str]

    assert bind(U, '1') == 1
    assert bind(U, 'abc') == 'abc'


def test_any():
    assert bind(Any, {'foo': 'bar'}) == {'foo': 'bar'}


def test_isnamedtuple():
    N = NamedTuple('N', [('a', str)])

    assert is_namedtuple(N)
    assert not is_namedtuple(tuple)
