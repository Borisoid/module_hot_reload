import importlib
from collections import defaultdict
from pathlib import Path
from threading import RLock
from types import ModuleType
from typing import Any, Dict, Sequence, Set, Union

from .utils import dirname, is_path_in_path, locked_method


T_a_rl = Dict[Any, RLock]
T_mt_t_mwb = Dict[ModuleType, Dict[type, 'ModuleWrapperBase']]
T_mt_aa = Dict[ModuleType, 'ModuleAttributeAccessor']
T_mt_mwb_maa = Union[ModuleType, 'ModuleWrapperBase', 'ModuleAttributeAccessor']
T_mwb_set = Set['ModuleWrapperBase']


class Storage:
    _module_rlock_mapping: T_a_rl = defaultdict(RLock)

    @classmethod
    def get_rlock(cls, obj: Any) -> RLock:
        return cls._module_rlock_mapping[obj]


def extract_module(module: T_mt_mwb_maa) -> ModuleType:
    if isinstance(module, ModuleType):
        return module
    else:
        # so it works with ModuleAttributeAccessor
        return object.__getattribute__(module, 'module')  


def recursive_locked_module_iterator(module: ModuleType):
    with Storage.get_rlock(module):
        yield module
        for attribute_name in dir(module):
            attribute = getattr(module, attribute_name)
            if (
                type(attribute) is ModuleType and
                hasattr(attribute, '__file__') and
                is_path_in_path(
                    dirname(Path(module.__file__).resolve()),
                    dirname(Path(attribute.__file__).resolve())
                )
            ):
                yield from recursive_locked_module_iterator(attribute)


class ModuleWrapperMeta(type):
    """
    For each wrapped module keeps a single instance of each class
    the module has been wrapped with.
    Basically singleton but there is an instance per wrapped module.
    """
    _modules_classes_instances: T_mt_t_mwb = defaultdict(dict)
    _all_instances: T_mwb_set = set()

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
    def before_reload_included(cls, module: 'ModuleWrapperBase') -> None:
        for instance in cls._all_instances:
            if set(instance.get_included_modules()).intersection(
                set(module.get_included_modules())
            ):
                instance.before_reload_included(module)

    @classmethod
    def after_reload_included(cls, module: 'ModuleWrapperBase') -> None:
        for instance in cls._all_instances:
            if set(instance.get_included_modules()).intersection(
                set(module.get_included_modules())
            ):
                instance.after_reload_included(module)


class ModuleWrapperBase(metaclass=ModuleWrapperMeta):
    def __init__(self, module: ModuleType):
        self.lock = Storage.get_rlock(module)
        self.module = module
        self.path = Path(module.__file__).resolve()
        self.is_dir = self.path.name == '__init__.py'
        self.is_file = not self.is_dir
        self.included_modules: Sequence[ModuleType] = tuple()
        self.update_included_modules()

    @locked_method()
    def update_included_modules(self) -> None:
        raise NotImplementedError('This is a base class. Override this method')

    @locked_method()
    def get_included_modules(self) -> Sequence[ModuleType]:
        return self.included_modules

    @locked_method()
    def get_included_locks(self):
        return set(Storage.get_rlock(m) for m in self.get_included_modules())

    @locked_method()
    def locked_set(self, name: str, value: Any) -> None:
        setattr(self.module, name, value)

    @locked_method()
    def locked_get(self, name: str) -> Any:
        return getattr(self.module, name)

    @locked_method()
    def reload(self) -> None:
        ModuleWrapperMeta.before_reload_included(self)

        locks = self.get_included_locks()

        try:
            for l in locks:
                l.acquire()

            self.do_reload()

        finally:
            for l in locks:
                l.release()

        ModuleWrapperMeta.after_reload_included(self)

    @locked_method()
    def before_reload_included(self, initiator: 'ModuleWrapperBase') -> None:
        """Called before do_reload() of this instance
        for all ModuleWrapperBase instances whose included_modules intersect
        with this instance's included_modules
        """

    @locked_method()
    def do_reload(self) -> None:
        raise NotImplementedError('This is a base class. Override this method')

    @locked_method()
    def do_reload_except(self, e: BaseException) -> None:
        raise e

    @locked_method()
    def after_reload_included(self, initiator: 'ModuleWrapperBase') -> None:
        """Called after do_reload() of this instance
        for all ModuleWrapperBase instances whose included_modules intersect
        with this instance's included_modules
        """

    @locked_method()
    def retrieved(self) -> None:
        pass


class AllModulesRecursiveUpdateMixin:
    @locked_method()
    def update_included_modules(self) -> None:
        self.included_modules = tuple(recursive_locked_module_iterator(self.module))


class DirModulesRecursiveUpdateMixin:
    @locked_method()
    def update_included_modules(self) -> None:
        if self.is_dir:
            self.included_modules = tuple(recursive_locked_module_iterator(self.module))
        else:  # if self.is_file
            self.included_modules = tuple((self.module,))


class StandardDoReloadMixin:
    @locked_method()
    def do_reload(self) -> None:
        for m in self.get_included_modules()[::-1]:
            try:
                importlib.reload(m)
            except Exception as e:
                self.do_reload_except(e)
        
    @locked_method()
    def do_reload_except(self, e: BaseException) -> None:
        pass


class NewModuleAwarenessMixin:
    def __init__(self, module: ModuleType):
        super().__init__(module)
        self._included_modules_obsolete = False

    @locked_method()
    def before_reload_included(self, initiator: ModuleWrapperBase) -> None:
        self._included_modules_obsolete = True

    @locked_method()
    def get_included_modules(self) -> Sequence[ModuleType]:
        if self._included_modules_obsolete:
            self.update_included_modules()
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
        module = extract_module(module)
        super().__setattr__('module', module)
        super().__setattr__('lock', Storage.get_rlock(module))

    def __getattribute__(self, name: str) -> Any:
        with super().__getattribute__('lock'):
            return getattr(super().__getattribute__('module'), name)

    def __setattr__(self, name: str, value: Any) -> None:
        with super().__getattribute__('lock'):
            setattr(super().__getattribute__('module'), name, value)
