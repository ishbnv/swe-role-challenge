"""Frozen launcher. Module selection and resource lifetime belong to apps."""

import sys

from apps.composition import open_cli

if __name__ == "__main__":
    with open_cli() as cli:
        print(cli.run(sys.argv[1:]))
