# cd to this directory
# run this file

# this is to include actual module into module search path ####################
import sys
from pathlib import Path
sys.path.insert(0, str(Path('../').resolve()))
###############################################################################

from module_hot_reload.reloaders import (
    NewModuleAwareAllModulesRecursiveAutomaticReloader,
)

import example_1
import example_2


r = NewModuleAwareAllModulesRecursiveAutomaticReloader()
# w = r.module_wrapper_class

example_1 = r.register(example_1)
example_2 = r.register(example_2)
r.start()

while True:
    print('example_1.e1 ', example_1.e1)
    print('example_2.e2 ', example_2.e2)
    print('example_2_1.e21 ', example_2.e21)
    print('example_2_2.e22 ', example_2.e22)
    input('waiting..........')
