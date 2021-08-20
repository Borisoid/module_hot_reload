from pathlib import Path
from threading import Lock
from types import ModuleType


def is_path_in_path(path_1: Path, path_2: Path) -> bool:
    path_1 = str(path_1.resolve())
    path_2 = str(path_2.resolve())
    return path_1 in path_2


def dirname(path: Path):
    if path.is_dir():
        return path
    if path.is_file():
        return path.parent


def has_instance_of_class(module: ModuleType, cls: type):
    for attribute_name in dir(module):
        attribute = getattr(module, attribute_name)
        if isinstance(attribute, cls):
            return True
    return False


def locked_method(lock_attribute_name: str = 'lock'):
    def decorator(func):
        def decorated(self, *args, **kwargs):
            with getattr(self, lock_attribute_name):
                return func(self, *args, **kwargs)
        return decorated
    return decorator


def optionally_locked_method(locked_default: bool = True, lock_attribute_name: str = 'lock'):
    def decorator(func):
        def decorated(self, *args, locked: bool = locked_default, **kwargs):
            if locked:
                getattr(self, lock_attribute_name).acquire()
            res = func(self, *args, **kwargs)
            if locked:
                getattr(self, lock_attribute_name).release()
            return res
        return decorated
    return decorator
