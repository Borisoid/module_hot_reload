from pathlib import Path
from types import ModuleType
from typing import Dict, Set, Union

from watchdog.observers import Observer
from watchdog.observers.api import ObservedWatch

from .module_wrappers import (
    ModuleWrapperBase,
    StandardModuleWrapper,
)
from .utils import (
    get_caller_path,
    has_instances_of_class,
    recursive_module_iterator,
)
from .watchdog_handlers import (
    DirModifiedHandler,
    FileModifiedHandler,
)


T_mt_mwb = Union[ModuleType, ModuleWrapperBase]


class ReloaderBase:
    module_wrapper_class: ModuleWrapperBase = StandardModuleWrapper

    def __init__(self):
        self.registered_modules: Set[ModuleType] = set()

    def _can_register(
        self, module: T_mt_mwb, calling_module_path: Path, raise_exception=False
    ):
        module = self.module_wrapper_class(module)
        try:
            for m in recursive_module_iterator(module.module):
                m_path = Path(m.__file__)
                assert m_path != calling_module_path, (
                    f'Cannot register {module.module!s} for registration attempt '
                    f'is made in one of files to be registered - {m_path!s}' 
                )

            assert not has_instances_of_class(module.module, ReloaderBase), (
                'Cannot register module that contains reloader instance'
            )
            assert module.module not in self.registered_modules, (
                f'Module {module.module!s} is already registered'
            )

            for m in self.registered_modules:
                duplicates = self.module_wrapper_class(m).file_paths.intersection(module.file_paths)
                assert not duplicates, f'These files are already registered: {list(map(str, duplicates))}'
            
            return True
        except AssertionError as e:
            if raise_exception:
                raise e
            else:
                return False

    def can_register(self, module: T_mt_mwb, raise_exception=False):
        """
        For direct use only - <reloader_instance>.can_register(...)

        The result depends on current reloader state, module this method
        is called in, attributes of <module> argument
        """
        return self._can_register(module, get_caller_path(1), raise_exception)

    def register(self, module: T_mt_mwb):
        raise NotImplementedError('This is a base class. Override this method')

    def unregister(self, module: T_mt_mwb):
        raise NotImplementedError('This is a base class. Override this method')


class OnModifiedReloader(ReloaderBase):
    """
    Watches registered modules and reloads them on change.
    Reload is done via importlib.reload(), read about reloaded modules' behaveour in the docs.
        https://docs.python.org/3/library/importlib.html#importlib.reload
    """
    def __init__(self):
        super().__init__()
        self.observer = Observer()
        self.watches: Dict[ModuleType, ObservedWatch] = {}

    def register(self, module: T_mt_mwb):
        calling_module_path = get_caller_path(1)
        self._can_register(module, calling_module_path, raise_exception=True)

        module = self.module_wrapper_class(module)

        if module.is_file:

            watch = self.observer.schedule(
                FileModifiedHandler(str(module.path), module.reload),
                str(module.path.parent),
            )

        if module.is_dir:
            path = module.path.parent  # module.path -- whatever/__init__.py

            watch = self.observer.schedule(
                DirModifiedHandler(str(path), module.reload),
                str(path),
                recursive=True,
            )

        self.watches[module.module] = watch
        self.registered_modules.add(module.module)

    def unregister(self, module: T_mt_mwb):
        module = self.module_wrapper_class(module)
        self.registered_modules.pop(module.module)
        watch = self.watches.pop(module.module)
        self.observer.unschedule(watch)

    def start(self):
        self.observer.start()

    def stop(self):
        self.observer.stop()


class ManualReloader(ReloaderBase):
    def register(self, module: T_mt_mwb):
        calling_module_path = get_caller_path(1)
        self._can_register(module, calling_module_path, raise_exception=True)

        module = self.module_wrapper_class(module)
        self.registered_modules.add(module.module)

    def unregister(self, module: T_mt_mwb):
        module = self.module_wrapper_class(module)
        self.registered_modules.pop(module.module)

    def reload(self):
        for m in self.registered_modules:
            self.module_wrapper_class(m).reload()
