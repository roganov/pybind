from typing import get_type_hints, Union, Tuple, List


class PybindError(Exception):
    pass


MISSING = object()


def make_binder_optional(binder):
    def x(value):
        if value is MISSING:
            return None
        try:
            return binder(value)
        except TypeError:
            return None
    return x


NoneType = type(None)


def try_unwrap_optional(cls):
    if getattr(cls, '__origin__', None) is Union:
        args = cls.__args__
        if len(args) == 2:
            if args[0] is NoneType:
                return True, args[1]
            elif args[1] is NoneType:
                return True, args[0]
    return False, cls


def is_newtype(cls):
    return hasattr(cls, '__name__') and hasattr(cls, '__supertype__')


def get_binder(cls):
    is_optional, cls = try_unwrap_optional(cls)
    origin = getattr(cls, '__origin__', None)
    if cls in (str, bool, int, float):
        binder = cls
    elif origin is Tuple:
        binders = [get_binder(typ) for typ in cls.__args__]

        def binder(data):
            if not isinstance(data, (list, tuple)):
                raise PybindError('must be convertable to list')
            data = list(data)
            data += [MISSING] * (len(binders) - len(data))
            return tuple(b(d) for b, d in zip(binders, data))
    elif origin is List:
        element_binder = get_binder(cls.__args__[0])

        def binder(data):
            if not isinstance(data, (list, tuple)):
                raise PybindError('must be convertable to list')
            data = list(data)
            return [element_binder(d) for d in data]
    elif is_newtype(cls):
        binder = get_binder(cls.__supertype__)
    else:
        binders = {name: get_binder(type_)
                   for name, type_ in get_type_hints(cls).items()}

        def binder(data):
            try:
                inst = cls()
            except Exception:
                raise PybindError('class must define default constructor')

            for name, binder in binders.items():
                raw_value = data.get(name, MISSING)
                value = binder(raw_value)
                setattr(inst, name, value)

            return inst

    if is_optional:
        binder = make_binder_optional(binder)

    return binder


def bind(cls, data):
    return get_binder(cls)(data)
