# cd to this directory
# run this file

# this is to include actual module into module search path ####################
import sys
from pathlib import Path
sys.path.insert(0, str(Path('../').resolve()))
###############################################################################

from module_hot_reload.reloaders import NewModuleAwareOnModifiedReloader

import example_1
import example_2


r = NewModuleAwareOnModifiedReloader()
w = r.module_wrapper_class

r.register(example_1)
r.register(example_2)
r.start()

while True:
    print('example_1.e1 ', w(example_1).locked_get('e1'))
    print('example_2.e2 ', w(example_2).locked_get('e2'))
    print('example_2_1.e21 ', w(example_2).locked_get('e21'))
    print('example_2_2.e22 ', w(example_2).locked_get('e22'))
    input('waiting..........')
