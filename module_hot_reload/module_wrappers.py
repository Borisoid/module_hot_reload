import importlib
from collections import defaultdict
from pathlib import Path
from threading import Lock
from types import ModuleType
from typing import Any, Dict, Set, Union

from .utils import optionally_locked_method, recursive_module_iterator


T_mt_l = Dict[ModuleType, Lock]
T_mt_t_mwb = Dict[ModuleType, Dict[type, 'ModuleWrapperBase']]
T_mt_aa = Dict[ModuleType, 'ModuleAttributeAccessor']
T_mt_mwb_maa = Union[ModuleType, 'ModuleWrapperBase', 'ModuleAttributeAccessor']


def extract_module(module: T_mt_mwb_maa) -> ModuleType:
    if isinstance(module, ModuleType):
        return module
    else:
        # so it works with ModuleAttributeAccessor
        return object.__getattribute__(module, 'module')  


class Storage:
    _module_lock_mapping: T_mt_l = defaultdict(Lock)

    @classmethod
    def get_lock(cls, module: ModuleType) -> Lock:
        return cls._module_lock_mapping[module]


class ModuleWrapperMeta(type):
    """
    For each wrapped module keeps a single instance of each class
    the module has been wrapped with.
    Basically singleton but there is an instance per wrapped module.
    """
    _modules_classes_instances: T_mt_t_mwb = defaultdict(dict)
    _all_instances: Set['ModuleWrapperBase'] = set()

    def __call__(cls, module: T_mt_mwb_maa, *args, **kwargs) -> 'ModuleWrapperBase':
        module = extract_module(module)

        classes = cls._modules_classes_instances[module]
        if cls not in classes:
            classes[cls] = new_instance = super().__call__(module, *args, **kwargs)
            cls._all_instances.add(new_instance)
        instance = cls._modules_classes_instances[module][cls]
        instance.retrieved()
        return instance

    @classmethod
    def before_reload_module(cls, module: 'ModuleWrapperBase') -> None:
        for instance in cls._modules_classes_instances[module.module].values():
            instance.before_reload_module(module)

    @classmethod
    def after_reload_module(cls, module: 'ModuleWrapperBase') -> None:
        for instance in cls._modules_classes_instances[module.module].values():
            instance.after_reload_module(module)


class ModuleWrapperBase(metaclass=ModuleWrapperMeta):
    def __init__(self, module: ModuleType):
        self.lock = Storage.get_lock(module)
        self.module = module
        self.path = Path(module.__file__).resolve()
        self.is_dir = self.path.name == '__init__.py'
        self.is_file = not self.is_dir
        self.included_modules: Set[ModuleType] = set()
        self.update_included_modules()

    @optionally_locked_method()
    def update_included_modules(self) -> None:
        raise NotImplementedError('This is a base class. Override this method')

    @optionally_locked_method()
    def get_included_modules(self) -> Set[ModuleType]:
        return self.included_modules

    @optionally_locked_method()
    def get_included_locks(self):
        return set(Storage.get_lock(m) for m in self.get_included_modules(locked=False))

    def locked_set(self, name: str, value: Any) -> None:
        with self.lock:
            setattr(self.module, name, value)

    def locked_get(self, name: str) -> Any:
        with self.lock:
            return getattr(self.module, name)

    def reload(self) -> None:
        included_locks = self.get_included_locks()

        for l in included_locks:
            l.acquire()
        
        ModuleWrapperMeta.before_reload_module(self)
        self.do_reload()
        ModuleWrapperMeta.after_reload_module(self)

        for l in included_locks:
            l.release()

    def before_reload_module(self, initiator: 'ModuleWrapperBase') -> None:
        """Called before do_reload() of this instance
        for all ModuleWrapperBase instances whose included_modules intersect
        with this instance's included_modules
        """

    def do_reload(self) -> None:
        raise NotImplementedError('This is a base class. Override this method')

    def do_reload_except(self, e: BaseException) -> None:
        raise e

    def after_reload_module(self, initiator: 'ModuleWrapperBase') -> None:
        """Called after do_reload() of this instance
        for all ModuleWrapperBase instances whose included_modules intersect
        with this instance's included_modules
        """

    def retrieved(self) -> None:
        pass


class AllModulesRecursiveUpdateMixin:
    @optionally_locked_method()
    def update_included_modules(self) -> None:
        self.included_modules = set(recursive_module_iterator(self.module))


class DirModulesRecursiveUpdateMixin:
    @optionally_locked_method()
    def update_included_modules(self) -> None:
        if self.is_dir:
            self.included_modules = set(recursive_module_iterator(self.module))
        else:  # if self.is_file
            self.included_modules = {self.module}


class StandardDoReloadMixin:
    def do_reload(self) -> None:
        for m in self.get_included_modules(locked=False):
            try:
                importlib.reload(m)
            except Exception as e:
                self.do_reload_except(e)
        
    def do_reload_except(self, e: BaseException) -> None:
        pass


class NewModuleAwarenessMixin:
    def __init__(self, module: ModuleType):
        super().__init__(module)
        self._included_modules_obsolete = False

    def before_reload_module(self, initiator: ModuleWrapperBase) -> None:
        self._included_modules_obsolete = True

    @optionally_locked_method()
    def get_included_modules(self) -> Set[ModuleType]:
        if self._included_modules_obsolete:
            self.update_included_modules(locked=False)
            self._included_modules_obsolete = False
        return self.included_modules


class NewModuleUnawareAllModulesRecursiveStandardModuleWrapper(
    AllModulesRecursiveUpdateMixin,
    StandardDoReloadMixin,
    ModuleWrapperBase,
):
    """Does not keep track of modules added after this class' instantiation.
    Recursively reloads all modules not higher in the file system than wrapped one.
    """


class NewModuleAwareAllModulesRecursiveStandardModuleWrapper(
    NewModuleAwarenessMixin,
    NewModuleUnawareAllModulesRecursiveStandardModuleWrapper,
):
    """Keeps track of modules added after this class' instantiation.
    Recursively reloads all modules not higher in the file system than wrapped one.
    """


class NewModuleUnawareDirModulesRecursiveStandardModuleWrapper(
    DirModulesRecursiveUpdateMixin,
    StandardDoReloadMixin,
    ModuleWrapperBase,
):
    """Does not keep track of modules added after this class' instantiation.
    Recursively reloads dir modules not higher in the file system than wrapped one.
    Single file modules are reloaded with no recurson.
    """


class NewModuleAwareDirModulesRecursiveStandardModuleWrapper(
    NewModuleAwarenessMixin,
    NewModuleUnawareDirModulesRecursiveStandardModuleWrapper,
):
    """Keeps track of modules added after this class' instantiation.
    Recursively reloads dir modules not higher in the file system than wrapped one.
    Single file modules are reloaded with no recurson.
    """


# Accessors ###################################################################

class ModuleAttributeAccessorMeta(type):
    _instances: T_mt_aa = dict()

    def __call__(cls, module: T_mt_mwb_maa) -> 'ModuleAttributeAccessor':
        module = extract_module(module)
        instance = cls._instances.get(module)
        if not instance:
            instance = super().__call__(module)
            cls._instances[module] = instance
        return instance


class ModuleAttributeAccessor(metaclass=ModuleAttributeAccessorMeta):
    """
    Special wrapper used in cases when module's and wrapper's attribute names intersect.
    Allows to get as well as set module's attributes using respective lock with normal syntax:

    `module = AttributeAccessor(module)`

    `a = module.attribute`

    `module.attribute = 42`
    """

    def __init__(self, module: T_mt_mwb_maa):
        super().__setattr__('module', extract_module(module))
        super().__setattr__('lock', Storage.get_lock(module))

    def __getattribute__(self, name: str) -> Any:
        with super().__getattribute__('lock'):
            return getattr(super().__getattribute__('module'), name)

    def __setattr__(self, name: str, value: Any) -> None:
        with super().__getattribute__('lock'):
            setattr(super().__getattribute__('module'), name, value)
