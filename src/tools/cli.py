from __future__ import annotations

import argparse
import importlib
import inspect
import pkgutil
import sys

from tools import processing
from tools.common.logging import setup_logging
from tools.processing.base import Processor


def _discover_processors() -> dict[str, Processor]:
    """Import every module under `tools.processing` and collect Processor subclasses."""
    processors: dict[str, Processor] = {}
    for module_info in pkgutil.iter_modules(processing.__path__, prefix=f"{processing.__name__}."):
        if module_info.name.endswith(".base"):
            continue
        module = importlib.import_module(module_info.name)
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, Processor) and obj is not Processor:
                instance = obj()
                processors[instance.name] = instance
    return processors


def build_parser(processors: dict[str, Processor]) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tools", description="Collection of processing commands")
    parser.add_argument("--log-level", default="INFO", help="Logging level (default: INFO)")

    subparsers = parser.add_subparsers(dest="command", required=True)
    for proc in processors.values():
        sub = subparsers.add_parser(proc.name, help=proc.help)
        proc.add_arguments(sub)
    return parser


def main(argv: list[str] | None = None) -> int:
    processors = _discover_processors()
    parser = build_parser(processors)
    args = parser.parse_args(argv)

    setup_logging(args.log_level)

    processor = processors[args.command]
    return processor.run(args)


if __name__ == "__main__":
    sys.exit(main())
