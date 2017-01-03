from typing import get_type_hints, Union, Tuple, List, TypeVar, Type, Any, Optional, Dict, cast, Callable


class PybindError(Exception):
    pass


MISSING = object()


T = TypeVar('T')


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
    mro = cls.__mro__
    return len(mro) > 1 and mro[1] is tuple \
        and hasattr(cls, '_fields') \
        and hasattr(cls, '_field_types')


class BindersFactory:
    _cache: Dict[Type[Any], Binder[Any]]

    def __init__(self) -> None:
        self._cache = {}

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
        if cls in (str, bool, int, float):
            binder = cls  # type: ignore
        elif origin is Tuple:
            binder = self.create_tuple_binder(cls)
        elif origin is List:
            binder = self.create_list_binder(cls)
        elif is_newtype(cls):
            binder = self.create_newtype_binder(cls)
        elif is_namedtuple(cls):
            binder = self.created_namedtuple_binder(cls)
        else:
            binder = self.create_custom_class_binder(cls)  # type: ignore

        if is_optional:
            return make_binder_optional(binder)
        else:
            return make_binder_required(binder)

    def create_tuple_binder(self, cls: Type[Tuple[Any, ...]]) -> Binder[Tuple[Any, ...]]:
        args: List[Type[Any]] = cast(Any, cls).__args__
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


def bind(cls: Type[T], data: Any) -> T:
    return BindersFactory().get(cls)(data)
