import importlib
from collections import defaultdict
from pathlib import Path
from threading import Lock
from types import ModuleType
from typing import Dict, Set, Union

from .utils import optionally_locked_method, recursive_module_iterator


T_mt_l = Dict[ModuleType, Lock]
T_mt_t_mwb = Dict[ModuleType, Dict[type, 'ModuleWrapperBase']]
T_mt_mwb = Union[ModuleType, 'ModuleWrapperBase']


class ModuleWrapperMeta(type):
    """
    For each wrapped module keeps a single instance of each class
    the module has been wrapped with.
    Basically singleton but there is an instance per wrapped module.
    Also contains one lock per wrapped module.
    """
    _module_lock_mapping: T_mt_l = defaultdict(Lock)
    _modules_classes_instances: T_mt_t_mwb = defaultdict(dict)

    def __call__(cls, module: T_mt_mwb, *args, **kwargs):
        if not isinstance(module, ModuleType):
            module = module.module

        classes = cls._modules_classes_instances[module]
        if cls not in classes:
            classes[cls] = super().__call__(module, *args, **kwargs)
        instance = cls._modules_classes_instances[module][cls]
        instance.retrieved()
        return instance

    @classmethod
    def get_lock(cls, module: ModuleType):
        return cls._module_lock_mapping[module]

    @classmethod
    def before_reload_module(cls, module: 'ModuleWrapperBase'):
        for instance in cls._modules_classes_instances[module.module].values():
            instance.before_reload_module(module)

    @classmethod
    def after_reload_module(cls, module: 'ModuleWrapperBase'):
        for instance in cls._modules_classes_instances[module.module].values():
            instance.after_reload_module(module)


class ModuleWrapperBase(metaclass=ModuleWrapperMeta):
    def __init__(self, module: ModuleType):
        self.lock = ModuleWrapperMeta.get_lock(module)
        self.module = module
        self.path = Path(module.__file__).resolve()
        self.is_dir = self.path.name == '__init__.py'
        self.is_file = not self.is_dir
        self.included_modules: Set[ModuleType] = set()
        self.update_included_modules()

    @optionally_locked_method()
    def get_included_modules(self) -> Set[ModuleType]:
        return self.included_modules

    @optionally_locked_method()
    def update_included_modules(self) -> None:
        if self.is_dir:
            self.included_modules = set(recursive_module_iterator(self.module))
        else:  # if self.is_file:
            self.included_modules = set((self.module,))

    def locked_get(self, attribute_name: str):
        with self.lock:
            return getattr(self.module, attribute_name)

    def reload(self):
        with self.lock:
            self.before_reload_instance()
            ModuleWrapperMeta.before_reload_module(self)
            self.do_reload()
            self.after_reload_instance()
            ModuleWrapperMeta.after_reload_module(self)

    def before_reload_instance(self):
        """Is called before do_reload() of this class"""

    def before_reload_module(self, initiator: 'ModuleWrapperBase'):
        """Is called before do_reload() of any ModuleWrapperBase instance that wraps the same module"""

    def do_reload(self):
        raise NotImplementedError('This is a base class. Override this method')

    def after_reload_instance(self):
        """Is called after do_reload() of this class"""

    def after_reload_module(self, initiator: 'ModuleWrapperBase'):
        """Is called after do_reload() of any ModuleWrapperBase instance that wraps the same module"""

    def retrieved(self):
        pass


class StandardModuleWrapper(ModuleWrapperBase):
    """Wraps a module. Does not keep track of modules added after this class' instantiation"""
    def do_reload(self):
        try:
            for m in self.get_included_modules(locked=False):
                importlib.reload(m)
        except Exception:
            pass


class NewModuleAwareStandardModuleWrapper(StandardModuleWrapper):
    """Wraps a module. Keeps track of modules added after this class' instantiation"""
    def __init__(self, module: ModuleType):
        super().__init__(module)
        self._included_modules_obsolete = False

    def after_reload_module(self, initiator: ModuleWrapperBase):
        self._included_modules_obsolete = True

    @optionally_locked_method()
    def get_included_modules(self):
        if self._included_modules_obsolete:
            self.update_included_modules(locked=False)
            self._included_modules_obsolete = False
        return self.included_modules
