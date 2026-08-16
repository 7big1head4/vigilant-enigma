# Copyright (C) 2026 the Enigma authors
# SPDX-License-Identifier: GPL-2.0-or-later

"""``python3 -m enigma_sdk <module>`` — import a module of agents and serve.

The kernel spawns this; you rarely run it yourself. Importing the named
module is what populates the registry, so every ``@agent(...)`` class in it
(or in anything it imports) becomes a kind the kernel can spawn.

A module may also be given as a file path (``agents.py``), in which case its
directory is added to ``sys.path`` first.
"""

import importlib
import os
import sys

from .core import REGISTRY
from .worker import serve


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        sys.stderr.write(
            "usage: python3 -m enigma_sdk <module-or-path> [more-modules...]\n"
        )
        return 2

    for target in args:
        if target.endswith(".py") or os.path.sep in target:
            path = os.path.abspath(target)
            directory = os.path.dirname(path)
            if directory not in sys.path:
                sys.path.insert(0, directory)
            target = os.path.splitext(os.path.basename(path))[0]
        importlib.import_module(target)

    if not REGISTRY:
        sys.stderr.write(
            "enigma_sdk: %s registered no agents — did you forget @agent(...)?\n"
            % ", ".join(args)
        )
        return 1

    serve()
    return 0


if __name__ == "__main__":
    sys.exit(main())
