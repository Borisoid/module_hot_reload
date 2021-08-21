# module_hot_reload

Package for reloading other packages and modules while Python is running

## Installation

```shell
pip install module-hot-reload
```

## Usage

Instantiate reloader you need, import module that you want to be reloaded,
register it in reloader, start reloader

```python
from module_hot_reload.reloaders import (
    NewModuleAwareAllModulesRecursiveAutomaticReloader,
)

import example

r = NewModuleAwareAllModulesRecursiveAutomaticReloader()
example = r.register(example)
r.start()

while True:
    print('example.e ', example.e)
    input('waiting..........')
```

There are 2 types of module wrappers: (confusingly)`ModuleWrapper` - used
primarily for reloading of module and its submodules and does it thread-safely;
`ModuleAttributeAccessor` - provides thread-safe `.` operator and prevents
collisions of module and wrapper class attribute names.
Reloader's `register()` method returns module wrapped
with `ModuleAttributeAccessor`.

The "API-methods" accept modules and know how to extract one form
ModuleWrapper or ModuleAttributeAccessor. So you can safely do something like

```python
from module_hot_reload.reloaders import (
    NewModuleAwareAllModulesRecursiveAutomaticReloader,
    NewModuleAwareAllModulesRecursiveManualReloader,
)
from module_hot_reload.module_wrappers import (
    ModuleAttributeAccessor,
    NewModuleAwareAllModulesRecursiveStandardModuleWrapper,
)

import example


r = NewModuleAwareAllModulesRecursiveAutomaticReloader()
w = r.module_wrapper_class

example = w(example)
# example is a ModuleWrapperBase instance now

example = r.register(example)
# example is a ModuleAttributeAccessor instance now

example = w(example)
# example is a ModuleWrapperBase instance now

#  \/  code sample continues  \/
```

As mentioned above, `ModuleAttributeAccessor` provides thread-safe `.`
operator.
`ModuleWrapper` does provide same functionality as well but with bulkier
syntax.

```python
#  /\  code sample continuation /\

example = ModuleAttributeAccessor(example)
print(example.e)  # with ModuleAttributeAccessor

example = w(example)
print(example.locked_get('e'))  # with ModuleWrapperBase

#  \/  code sample continues  \/
```

The question is: "Why would you need to use `ModuleWrapper` then?".
You really don't need to. Using it you have the ability to manually reload
the module and access its attributes; but there are manual reoaders whose
`register()` method still returns `ModuleAttributeAccessor`.

```python
#  /\  code sample continuation /\

mr = NewModuleAwareAllModulesRecursiveManualReloader()
example = mr.register(example)
mr.reload()
print(example.e)

# is equivalent to

mw = mr.module_wrapper_class
example = mw(example)
example.reload()
print(example.locked_get('e'))
```
