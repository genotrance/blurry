"App initialization with reload support"

# Standard library imports
import importlib
import sys

# Package imports
from . import version
from . import helper
from . import similar as sim
from . import image
from . import gui
from . import main

def startup():
    "Main entry point that reloads if requested"
    args = sys.argv[1:]
    while True:
        blurry = main.Blurry(args)
        blurry.start()
        if blurry.is_reload is False:
            break

        for module in [version, helper, sim, image, gui, main]:
            importlib.reload(module)
            globals().update(vars(module))
