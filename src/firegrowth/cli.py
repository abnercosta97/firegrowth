"""Interface de linha de comando para validação do dataset."""

import argparse
import json

from . import __version__
from .analysis import run_exploratory_analysis
from .data import validate_release
from .pipeline import prepare_event_daily, run_benchmark


def main() -> None:
    parser = argparse.ArgumentParser(prog="firegrowth")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command")
    check = sub.add_parser("validate", help="validate a local dataset release")
    check.add_argument("root")
    prepare = sub.add_parser("prepare", help="build event-day cumulative areas")
    prepare.add_argument("dataset")
    prepare.add_argument("output")
    run = sub.add_parser("run", help="run the baseline benchmark")
    run.add_argument("dataset")
    run.add_argument("output")
    run.add_argument("--horizons", default="1,3")
    analyze = sub.add_parser("analyze", help="generate descriptive event statistics")
    analyze.add_argument("dataset")
    analyze.add_argument("benchmark")
    analyze.add_argument("report")
    args = parser.parse_args()
    if args.command == "validate":
        result = validate_release(args.root)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if not result["valid"]:
            raise SystemExit(1)
    elif args.command == "prepare":
        print(json.dumps(prepare_event_daily(args.dataset, args.output), indent=2))
    elif args.command == "run":
        horizons = [int(value) for value in args.horizons.split(",")]
        print(json.dumps(run_benchmark(args.dataset, args.output, horizons), indent=2))
    elif args.command == "analyze":
        print(
            json.dumps(
                run_exploratory_analysis(args.dataset, args.benchmark, args.report),
                indent=2,
            )
        )
    else:
        parser.print_help()
