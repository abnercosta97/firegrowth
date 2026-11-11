"""Interface de linha de comando para validação do dataset."""

import argparse
import json

from . import __version__
from .data import validate_release


def main() -> None:
    parser = argparse.ArgumentParser(prog="firegrowth")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command")
    check = sub.add_parser("validate", help="validate a local dataset release")
    check.add_argument("root")
    args = parser.parse_args()
    if args.command == "validate":
        result = validate_release(args.root)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if not result["valid"]:
            raise SystemExit(1)
    else:
        parser.print_help()
