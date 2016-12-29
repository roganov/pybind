from typing import get_type_hints, Optional, Union


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


def get_binder(cls):
    is_optional, cls = try_unwrap_optional(cls)
    if cls in (str, bool, int, float):
        binder = cls
    else:
        def binder(data):
            annotations = get_type_hints(cls)

            try:
                inst = cls()
            except Exception:
                raise PybindError('class must define default constructor')

            for name, type_ in annotations.items():
                binder = get_binder(type_)
                raw_value = data.get(name, MISSING)
                value = binder(raw_value)
                setattr(inst, name, value)

            return inst
    if is_optional:
        binder = make_binder_optional(binder)

    return binder


def bind(cls, data):
    return get_binder(cls)(data)
