from types import ModuleType
from typing import Dict, Set, Union

from watchdog.observers import Observer
from watchdog.observers.api import ObservedWatch

from .module_wrappers import (
    ModuleAttributeAccessor,
    ModuleWrapperBase,
    NewModuleAwareAllModulesRecursiveStandardModuleWrapper,
    NewModuleAwareDirModulesRecursiveStandardModuleWrapper,
    NewModuleUnawareAllModulesRecursiveStandardModuleWrapper,
    NewModuleUnawareDirModulesRecursiveStandardModuleWrapper,
)
from .utils import has_instance_of_class
from .watchdog_handlers import (
    DirModifiedHandler,
    FileModifiedHandler,
    NewModuleAwareDirModifiedHandler,
)


T_mt_mwb_maa = Union[ModuleType, ModuleWrapperBase, ModuleAttributeAccessor]


class ReloaderBase:
    module_wrapper_class: ModuleWrapperBase = None

    def __init__(self):
        self.registered_modules: Set[ModuleType] = set()

    def can_register(self, module: T_mt_mwb_maa, raise_exception: bool = False) -> bool:
        """
        The result depends on current reloader state, module this method
        is called in, attributes of <module> argument
        """
        module = self.module_wrapper_class(module)
        try:
            assert not has_instance_of_class(module.module, ReloaderBase), (
                'Cannot register module that contains reloader instance'
            )
            assert module.module not in self.registered_modules, (
                f'{module.module!s} is already registered'
            )

            for m in self.registered_modules:
                duplicates: Set[ModuleType] = (
                    self.module_wrapper_class(m)
                    .get_included_modules()
                    .intersection(module.get_included_modules())
                )
                assert not duplicates, (
                    f'These modules are already registered: '
                    f'{list(map(str, duplicates))}'
                )

            return True

        except AssertionError as e:
            if raise_exception:
                raise e
            else:
                return False

    def register(self, module: T_mt_mwb_maa) -> ModuleAttributeAccessor:
        raise NotImplementedError('This is a base class. Override this method')

    def unregister(self, module: T_mt_mwb_maa) -> None:
        raise NotImplementedError('This is a base class. Override this method')


# Automatic Reloaders #########################################################

class AutomaticReloaderMixin(ReloaderBase):
    def __init__(self):
        super().__init__()
        self.observer = Observer()
        self.watches: Dict[ModuleType, ObservedWatch] = {}

    def register(self, module: T_mt_mwb_maa) -> ModuleAttributeAccessor:
        module = self.module_wrapper_class(module)
        self.can_register(module, raise_exception=True)

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
        return ModuleAttributeAccessor(module)

    def unregister(self, module: T_mt_mwb_maa) -> None:
        module = self.module_wrapper_class(module)
        self.registered_modules.pop(module.module)
        watch = self.watches.pop(module.module)
        self.observer.unschedule(watch)

    def set_daemon(self, daemonic: bool) -> None:
        self.observer.setDaemon(daemonic)

    def start(self) -> None:
        self.observer.start()

    def stop(self) -> None:
        self.observer.stop()

    def join(self, *args, **kwargs) -> None:
        self.observer.join(*args, **kwargs)


class NewModuleUnawareAllModulesRecursiveAutomaticReloader(AutomaticReloaderMixin):
    """
    Watches registered modules and reloads them on change.
    Does not keep track of modules added during it's work.
    Reload is done via importlib.reload(), read about reloaded modules' behaveour in the docs.
        https://docs.python.org/3/library/importlib.html#importlib.reload
    """
    module_wrapper_class: ModuleWrapperBase = \
        NewModuleUnawareAllModulesRecursiveStandardModuleWrapper
    file_handler = FileModifiedHandler
    dir_handler = DirModifiedHandler

    
class NewModuleAwareAllModulesRecursiveAutomaticReloader(
    NewModuleUnawareAllModulesRecursiveAutomaticReloader,
):
    """
    Watches registered modules and reloads them on change.
    Keeps track of modules added during it's work.
    Reload is done via importlib.reload(), read about reloaded modules' behaveour in the docs.
        https://docs.python.org/3/library/importlib.html#importlib.reload
    """
    module_wrapper_class: ModuleWrapperBase = \
        NewModuleAwareAllModulesRecursiveStandardModuleWrapper
    dir_handler = NewModuleAwareDirModifiedHandler


class NewModuleUnawareDirModulesRecursiveAutomaticReloader(AutomaticReloaderMixin):
    module_wrapper_class: ModuleWrapperBase = \
        NewModuleUnawareDirModulesRecursiveStandardModuleWrapper
    file_handler = FileModifiedHandler
    dir_handler = DirModifiedHandler


class NewModuleAwareDirModulesRecursiveAutomaticReloader(
    NewModuleUnawareDirModulesRecursiveAutomaticReloader,
):
    module_wrapper_class: ModuleWrapperBase = \
        NewModuleAwareDirModulesRecursiveStandardModuleWrapper
    dir_handler = NewModuleAwareDirModifiedHandler


# Manual Reloaders ############################################################

class ManualReloaderMixin(ReloaderBase):
    def register(self, module: T_mt_mwb_maa) -> ModuleAttributeAccessor:
        module = self.module_wrapper_class(module)
        self.can_register(module, raise_exception=True)
        self.registered_modules.add(module.module)
        return ModuleAttributeAccessor(module)

    def unregister(self, module: T_mt_mwb_maa) -> None:
        module = self.module_wrapper_class(module)
        self.registered_modules.pop(module.module)

    def reload(self) -> None:
        for m in self.registered_modules:
            self.module_wrapper_class(m).reload()


class NewModuleUnawareAllModulesRecursiveManualReloader(ManualReloaderMixin):
    module_wrapper_class: ModuleWrapperBase = \
        NewModuleUnawareAllModulesRecursiveStandardModuleWrapper


class NewModuleAwareAllModulesRecursiveManualReloader(ManualReloaderMixin):
    module_wrapper_class: ModuleWrapperBase = \
        NewModuleAwareAllModulesRecursiveStandardModuleWrapper

    
class NewModuleUnawareDirModulesRecursiveManualReloader(ManualReloaderMixin):
    module_wrapper_class: ModuleWrapperBase = \
        NewModuleUnawareDirModulesRecursiveStandardModuleWrapper


class NewModuleAwareDirModulesRecursiveManualReloader(ManualReloaderMixin):
    module_wrapper_class: ModuleWrapperBase = \
        NewModuleAwareDirModulesRecursiveStandardModuleWrapper
