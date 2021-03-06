from contextlib import contextmanager
from datetime import datetime, date
from decimal import Decimal
from enum import Enum, IntEnum
from typing import Optional, Tuple, List, NewType, NamedTuple, Union, Any

import pytest

from pybind import bind, try_unwrap_optional, is_namedtuple, PybindError


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

    @pytest.mark.xfail
    def test_subclass(self):
        xx = bind(self.XX, {'a': '1', 'b': 'b', 'c': 'c'})

        assert xx == self.XX(a=1, b='b', c='c')


def test_union():
    U = Union[int, str]

    assert bind(U, '1') == 1
    assert bind(U, 'abc') == 'abc'


def test_any():
    assert bind(Any, {'foo': 'bar'}) == {'foo': 'bar'}


def test_decimal():
    assert bind(Decimal, '1.1') == Decimal('1.1')


def test_datetime():
    expected = datetime(year=2016, month=1, day=1, hour=0, minute=0)
    assert bind(datetime, '2016-01-01T00:00:00') == expected
    # TODO: with seconds


def test_date():
    assert bind(date, '2016-01-01') == date(year=2016, month=1, day=1)


def test_enum():
    class X(Enum):
        a = '1'

    assert bind(X, '1') == X.a


def test_int_enum():
    class X(IntEnum):
        a = 1
        b = 2

    assert bind(X, '1') == X.a


def test_isnamedtuple():
    N = NamedTuple('N', [('a', str)])

    assert is_namedtuple(N)
    assert not is_namedtuple(tuple)


def test_variable_length_tuple():
    xs = bind(Tuple[int, ...], ['1', '2', '3'])
    assert xs == (1, 2, 3)

    xs = bind(Tuple[str, ...], [])
    assert xs == ()

    with pytest.raises(PybindError):
        bind(Tuple[str, ...], 'not a list or tuple')


@contextmanager
def invalid_as(error_code):
    with pytest.raises(PybindError) as excinfo:
        yield
    assert excinfo.value.args[0] == error_code


class TestStringBinding:

    def test_None_invalid(self):
        with invalid_as('required'):
            bind(str, None)

    def test_whitespaces_invalid(self):
        with invalid_as('required'):
            bind(str, ' \n \t')



def test_bind_raw_dict():
    d = bind(dict, {1: 1})
    assert d == {1: 1}
