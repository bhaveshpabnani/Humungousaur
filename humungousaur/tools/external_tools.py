import sys

from humungousaur.tools.external import implementation

sys.modules[__name__] = implementation
