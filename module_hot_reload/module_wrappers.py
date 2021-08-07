import importlib
from collections import defaultdict
from pathlib import Path
from threading import Lock
from types import ModuleType
from typing import Dict, Set, Union

from .utils import recursive_module_iterator

T_mt_l = Dict[ModuleType, Lock]
T_mt_t_mwb = Dict[ModuleType, Dict[type, 'ModuleWrapperBase']]
T_mt_mwb = Union[ModuleType, 'ModuleWrapperBase']


class ModuleWrapperMeta(type):
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
    def reloaded(cls, module: ModuleType):
        for instance in cls._modules_classes_instances[module].values():
            instance.after_reload()


class ModuleWrapperBase(metaclass=ModuleWrapperMeta):
    def __init__(self, module: ModuleType):
        self.module = module
        self.lock = ModuleWrapperMeta.get_lock(module)
        self.path = Path(module.__file__)
        self.is_dir = self.path.name == '__init__.py'
        self.is_file = not self.is_dir
        self._file_paths = self.get_file_paths()
        
    @property
    def file_paths(self):
        return self._file_paths

    def get_file_paths(self) -> Set[Path]:
        print('get_file_paths')
        if self.is_dir:
            file_paths = set(map(
                lambda m: Path(m.__file__),
                recursive_module_iterator(self.module)
            ))
        else:  # if self.is_file:
            file_paths = set((self.path,))

        return file_paths

    def locked_get(self, attribute_name: str):
        with self.lock:
            return getattr(self.module, attribute_name)

    def reload(self):
        with self.lock:
            self.do_reload()
            ModuleWrapperMeta.reloaded(self.module)

    def do_reload(self):
        raise NotImplementedError('This is a base class. Override this method')

    def after_reload(self):
        """Is called after do_reload() of any ModuleWrapperBase instance that wraps the same module"""

    def retrieved(self):
        pass


class StandardModuleWrapper(ModuleWrapperBase):
    def __init__(self, module: ModuleType):
        super().__init__(module)
        if self.is_file:
            self.modules_to_reload = list((self.module,))
        if self.is_dir:
            self.modules_to_reload = list(recursive_module_iterator(self.module))

    def do_reload(self):
        try:
            for m in self.modules_to_reload:
                importlib.reload(m)
        except Exception:
            pass


class NewModuleAwareStandardModuleWrapper(ModuleWrapperBase):
    def __init__(self, module: ModuleType):
        super().__init__(module)
        self.file_paths_obsolete = False

    def do_reload(self):
        try:
            if self.is_file:
                importlib.reload(self.module)
            if self.is_dir:
                for m in recursive_module_iterator(self.module):
                    importlib.reload(m)
        except Exception:
            pass

    def after_reload(self):
        self.file_paths_obsolete = True

    @property
    def file_paths(self):
        with self.lock:
            if self.file_paths_obsolete:    
                self._file_paths = self.get_file_paths()
                self.file_paths_obsolete = False
        return super().file_paths
