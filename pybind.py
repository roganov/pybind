import datetime
import inspect
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, TypeVar, \
    Union, cast, get_type_hints

import enum

from errors import Errors


class PybindError(Exception):
    """Binding failed"""
    pass


class ConfigError(Exception):
    """Some kind of configuration error, for example
    when binding target is not possible to bind to.
    """

MISSING = object()


T = TypeVar('T')
TEnum = TypeVar('TEnum', bound=enum.Enum)


Binder = Callable[[Any], T]


def make_binder_optional(binder: Binder[T]) -> Binder[Optional[T]]:
    def optional_binder(value: Any) -> Optional[T]:
        if value is MISSING:
            return None
        try:
            return binder(value)
        except TypeError:
            return None
    return optional_binder


def make_binder_required(binder: Binder[T]) -> Binder[T]:
    def required_binder(value: Any) -> T:
        if value is MISSING:
            raise PybindError('value is missing, but required')
        return binder(value)
    return required_binder


NoneType = type(None)


def try_unwrap_optional(cls: Type[Any]) -> Tuple[bool, Type[Any]]:
    if getattr(cls, '__origin__', None) is Union:
        args = cast(Any, cls).__args__
        if len(args) == 2:
            if args[0] is NoneType:
                return True, args[1]
            elif args[1] is NoneType:
                return True, args[0]
    return False, cls


def is_newtype(cls: Type[T]) -> bool:
    return hasattr(cls, '__name__') and hasattr(cls, '__supertype__')


def is_namedtuple(cls: Type[T]) -> bool:
    mro = getattr(cls, '__mro__', ())
    # It's kind of crappy but there is apparently no
    # better way to find out if a type is a typing.NamedTuple.
    return len(mro) > 1 and mro[1] is tuple \
        and hasattr(cls, '_fields') \
        and hasattr(cls, '_field_types')


class BindersFactory:
    _cache: Dict[Type[Any], Binder[Any]]

    def __init__(self) -> None:
        self._cache = {}
        self._binders_registry = {
            str: nonwhitespace_string_binder,
            bool: self.create_converting_binder(bool),
            int: self.create_converting_binder(int),
            float: self.create_converting_binder(float),
            Decimal: self.create_converting_binder(Decimal),
            datetime.date: self.create_date_binder('%Y-%m-%d'),
            datetime.datetime: self.create_datetime_binder('%Y-%m-%dT%H:%M:%S'),
        }

    def register_binder(self, cls: Type[T], binder: Binder[T]) -> None:
        self._cache = {}
        self._binders_registry[cls] = binder

    def get(self, cls: Type[T]) -> Binder[T]:
        try:
            return self._cache[cls]
        except KeyError:
            self._cache[cls] = b = self.create(cls)
            return b

    def create(self, cls: Type[T]) -> Binder[T]:
        is_optional, cls = try_unwrap_optional(cls)
        origin = getattr(cls, '__origin__', None)

        binder: Binder[Any]
        if cls in self._binders_registry:
            binder = self._binders_registry[cls]
        elif origin is Tuple:
            binder = self.create_tuple_binder(cls)
        elif origin is List:
            binder = self.create_list_binder(cls)
        elif origin is Union:
            binder = self.create_union_binder(cls)
        elif is_newtype(cls):
            binder = self.create_newtype_binder(cls)
        elif is_namedtuple(cls):
            binder = self.created_namedtuple_binder(cls)
        elif cls is Any:
            binder = self.create_any_binder()
        elif isinstance(cls, type) and issubclass(cls, enum.Enum):
            binder = self.create_enum_binder(cls)
        else:
            binder = self.create_custom_class_binder(cls)

        if is_optional:
            binder = make_binder_optional(binder)
        else:
            binder = make_binder_required(binder)
        return binder  # type: ignore

    def create_converting_binder(self, cls: Callable[[Any], T]) -> Binder[T]:
        def binder(data: Any) -> T:
            if data is None:
                raise PybindError('cannot bind None value')
            try:
                return cls(data)
            except Exception:
                raise PybindError('unable to bind {data} to {cls}'
                                  .format(data=data,
                                          cls=cls))

        return binder

    def create_tuple_binder(self, cls: Type[Tuple[Any, ...]]) -> Binder[Tuple[Any, ...]]:
        args: List[Type[Any]] = cast(Any, cls).__args__
        is_variable_length_tuple = len(args) == 2 and args[1] is Ellipsis
        if is_variable_length_tuple:
            element_binder = self.get(args[0])

            def binder(data: Any) -> Tuple[Any, ...]:
                if not isinstance(data, (list, tuple)):
                    raise PybindError('must be convertable to list')
                return tuple(element_binder(d) for d in data)

        else:
            binders = [self.get(typ) for typ in args]

            def binder(data: Any) -> Tuple[Any, ...]:
                if not isinstance(data, (list, tuple)):
                    raise PybindError('must be convertable to list')
                data = list(data)
                data += [MISSING] * (len(binders) - len(data))
                return tuple(b(d) for b, d in zip(binders, data))

        return binder

    def create_list_binder(self, cls: Type[List[T]]) -> Binder[List[T]]:
        element_cls: Type[T] = cast(Any, cls).__args__[0]
        element_binder = self.get(element_cls)

        def binder(data: Any) -> List[T]:
            if not isinstance(data, (list, tuple)):
                raise PybindError('must be convertable to list')
            return [element_binder(d) for d in data]
        return binder

    def create_newtype_binder(self, cls: Type[T]) -> Binder[T]:
        sup: Type[Any] = cast(Any, cls).__supertype__
        return self.get(sup)

    def create_custom_class_binder(self, cls: Callable[..., T]) -> Binder[T]:
        if inspect.isabstract(cls):
            raise ConfigError('abstract classes are not supported')
        has_default_constructor = cls.__init__ is object.__init__  # type: ignore
        if not has_default_constructor:
            raise PybindError('{cls} must have default constructor'
                              .format(cls=cls))

        binders: Dict[str, Binder[Any]] = \
            {name: self.get(type_)
             for name, type_ in get_type_hints(cls).items()}

        def binder(data: Any) -> T:
            try:
                inst = cls()
            except Exception:
                raise PybindError('class must define default constructor')

            for name, binder in binders.items():
                raw_value = data.get(name, MISSING)
                value = binder(raw_value)
                setattr(inst, name, value)
            return inst

        return binder

    def created_namedtuple_binder(self, cls: Type[T]) -> Binder[T]:
        annotations = cast(Any, cls)._field_types
        fields = cast(Any, cls)._fields
        if set(fields) != annotations.keys():
            raise PybindError(
                'some attributes of {cls} are missing type annotations'
                .format(cls=cls))
        binders = {name: self.get(type_)
                   for name, type_ in annotations.items()}

        def binder(data: Any) -> T:
            kwargs: Dict[str, Any]
            if isinstance(data, (list, tuple)):
                # Positional binding.
                data = list(data)
                data += [MISSING] * (len(fields) - len(data))
                kwargs = {
                    name: binders[name](d)
                    for name, d in zip(fields, data)
                }
            elif isinstance(data, dict):
                # Named binding.
                kwargs = {
                    name: binder(data.get(name, MISSING))
                    for name, binder in binders.items()
                }
            else:
                raise PybindError('unable to bind {data} to {cls}'
                                  .format(data=data, cls=cls))
            try:
                return cls(**kwargs)  # type: ignore
            except Exception:
                raise PybindError('exception when creating {cls}'
                                  .format(cls=cls))

        return binder

    def create_union_binder(self, cls: Type[T]) -> Binder[T]:
        union_types = cast(Any, cls).__args__
        binders = [self.get(t) for t in union_types]

        def binder(data: Any) -> T:
            for b in binders:
                try:
                    return b(data)  # type: ignore
                except PybindError:
                    continue
            raise PybindError('unable to bind {data} to {cls}'
                              .format(data=data, cls=cls))

        return binder

    def create_any_binder(self) -> Binder[Any]:
        return lambda x: x

    def create_date_binder(self, date_format: str) -> Binder[datetime.date]:
        def binder(data: Any) -> datetime.date:
            try:
                return datetime.datetime.strptime(str(data), date_format).date()
            except (ValueError, TypeError):
                raise PybindError()
        return binder

    def create_datetime_binder(self, date_format: str) -> Binder[datetime.datetime]:
        def binder(data: Any) -> datetime.datetime:
            try:
                return datetime.datetime.strptime(str(data), date_format)
            except (ValueError, TypeError):
                raise PybindError()
        return binder

    def create_enum_binder(self, cls: Type[TEnum]) -> Binder[TEnum]:
        if issubclass(cls, enum.IntEnum):
            def binder(data: Any) -> TEnum:
                try:
                    return cls(int(data))
                except (ValueError, TypeError):
                    raise PybindError()
        else:
            def binder(data: Any) -> TEnum:
                try:
                    return cls(data)
                except (ValueError, TypeError):
                    raise PybindError()
        return binder


def nonwhitespace_string_binder(data: Any) -> str:
    if data is None:
        raise PybindError('required')
    data = str(data).strip()
    if data == '':
        raise PybindError('required')
    return data  # type: ignore


def bind(cls: Type[T], data: Any) -> T:
    return BindersFactory().get(cls)(data)


# Ideas:
# - union validator
# - default values
