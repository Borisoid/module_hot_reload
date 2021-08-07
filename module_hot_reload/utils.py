from pathlib import Path
from types import ModuleType


def path_full_include(path_1: Path, path_2: Path) -> bool:
    """Basically `(path_1 in path_2) or (path_2 in path_1)`"""
    path_1 = str(path_1.resolve())
    path_2 = str(path_2.resolve())
    return path_1 in path_2 or path_2 in path_1

def dirname(path: Path):
    if path.is_dir():
        return path
    if path.is_file():
        return path.parent

def recursive_module_iterator(module: ModuleType):
    yield module
    for attribute_name in dir(module):
        attribute = getattr(module, attribute_name)
        if (
            type(attribute) is ModuleType and
            hasattr(attribute, '__file__') and
            path_full_include(
                dirname(Path(module.__file__)),
                dirname(Path(attribute.__file__))
            )
        ):
            for m in recursive_module_iterator(attribute):
                yield m

def has_instances_of_class(module: ModuleType, cls: type):
    for attribute_name in dir(module):
        attribute = getattr(module, attribute_name)
        if isinstance(attribute, cls):
            return True
    return False
