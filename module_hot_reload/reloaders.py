from types import ModuleType
from typing import Dict, Set, Union

from watchdog.observers import Observer
from watchdog.observers.api import ObservedWatch

from .module_wrappers import (
    ModuleWrapperBase,
    NewModuleAwareStandardModuleWrapper,
    StandardModuleWrapper,
)
from .utils import has_instances_of_class
from .watchdog_handlers import (
    DirModifiedHandler,
    FileModifiedHandler,
    NewModuleAwareDirHandler,
)


T_mt_mwb = Union[ModuleType, ModuleWrapperBase]


class ReloaderBase:
    module_wrapper_class: ModuleWrapperBase = None

    def __init__(self):
        self.registered_modules: Set[ModuleType] = set()

    def can_register(self, module: T_mt_mwb, raise_exception=False):
        """
        The result depends on current reloader state, module this method
        is called in, attributes of <module> argument
        """
        module = self.module_wrapper_class(module)
        try:
            assert not has_instances_of_class(module.module, ReloaderBase), (
                'Cannot register module that contains reloader instance'
            )
            assert module.module not in self.registered_modules, (
                f'Module {module.module!s} is already registered'
            )

            for m in self.registered_modules:
                duplicates = self.module_wrapper_class(m).file_paths.intersection(module.file_paths)
                assert not duplicates, (
                    f'These files are already registered: '
                    f'{list(map(str, duplicates))}'
                )

            return True

        except AssertionError as e:
            if raise_exception:
                raise e
            else:
                return False

    def register(self, module: T_mt_mwb):
        raise NotImplementedError('This is a base class. Override this method')

    def unregister(self, module: T_mt_mwb):
        raise NotImplementedError('This is a base class. Override this method')


class OnModifiedReloader(ReloaderBase):
    """
    Watches registered modules and reloads them on change.
    Does not keep track of modules added during it's work.
    Reload is done via importlib.reload(), read about reloaded modules' behaveour in the docs.
        https://docs.python.org/3/library/importlib.html#importlib.reload
    """
    module_wrapper_class: ModuleWrapperBase = StandardModuleWrapper
    file_handler = FileModifiedHandler
    dir_handler = DirModifiedHandler

    def __init__(self):
        super().__init__()
        self.observer = Observer()
        self.watches: Dict[ModuleType, ObservedWatch] = {}

    def register(self, module: T_mt_mwb):
        self.can_register(module, raise_exception=True)

        module = self.module_wrapper_class(module)

        if module.is_file:

            watch = self.observer.schedule(
                self.file_handler(module.reload, str(module.path)),
                str(module.path.parent),
            )

        if module.is_dir:
            path = module.path.parent  # module.path -- whatever/__init__.py

            watch = self.observer.schedule(
                self.dir_handler(module.reload, str(path)),
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


class NewModuleAwareOnModifiedReloader(OnModifiedReloader):
    """
    Watches registered modules and reloads them on change.
    Keeps track of modules added during it's work.
    Reload is done via importlib.reload(), read about reloaded modules' behaveour in the docs.
        https://docs.python.org/3/library/importlib.html#importlib.reload
    """
    module_wrapper_class = NewModuleAwareStandardModuleWrapper
    dir_handler = NewModuleAwareDirHandler


class ManualReloader(ReloaderBase):
    """
    Basically a container for reloadable module wrappers that allows to reload
    them all at once.
    Reload is done via importlib.reload(), read about reloaded modules' behaveour in the docs.
        https://docs.python.org/3/library/importlib.html#importlib.reload
    """
    def register(self, module: T_mt_mwb):
        self.can_register(module, raise_exception=True)

        module = self.module_wrapper_class(module)
        self.registered_modules.add(module.module)

    def unregister(self, module: T_mt_mwb):
        module = self.module_wrapper_class(module)
        self.registered_modules.pop(module.module)

    def reload(self):
        for m in self.registered_modules:
            self.module_wrapper_class(m).reload()
