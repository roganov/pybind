import copy
from contextlib import contextmanager


GLOBAL_ERROR_KEY = ''


class Errors:

    def __init__(self):
        self._errors = {}
        self._current_path = ()

    def add_error(self, error):
        es = self._errors
        for p in self._current_path:
            es = es.setdefault(p, {})
        es.setdefault(GLOBAL_ERROR_KEY, []).append(error)

    @contextmanager
    def with_path(self, path):
        self._current_path = self._current_path + (path, )
        try:
            yield
        finally:
            self._current_path = self._current_path[:-1]

    def __bool__(self):
        return bool(self._errors)

    @property
    def has_errors(self):
        return bool(self)

    @property
    def as_dict(self):
        return copy.deepcopy(self._errors)
