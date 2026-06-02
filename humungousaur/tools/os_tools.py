import sys

from humungousaur.tools.os_control import implementation

sys.modules[__name__] = implementation
