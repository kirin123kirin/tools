from __future__ import annotations

import argparse
import importlib
import inspect
import pkgutil
import sys
from pathlib import PureWindowsPath

from workpytools import processing
from workpytools.common.logging import setup_logging
from workpytools.processing.base import Processor


def _discover_processors() -> dict[str, Processor]:
    """Import every module under `workpytools.processing` and collect Processor subclasses."""
    processors: dict[str, Processor] = {}
    for module_info in pkgutil.iter_modules(processing.__path__, prefix=f"{processing.__name__}."):
        if module_info.name.endswith(".base"):
            continue
        try:
            module = importlib.import_module(module_info.name)
        except ImportError as exc:
            print(f"warning: skipping {module_info.name}: {exc}", file=sys.stderr)
            continue
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


_ENTRY_POINT_ALIASES = {
    # toolh.exe だけは他の1コマンド=1exe規則に沿わない特別なエントリーポイント名
    # （help.exe は分かりにくいので toolh とした）。
    "toolh": "help",
}


def run_as_subcommand() -> int:
    """Entry point for a per-command executable (e.g. `denoise.exe`).

    The subcommand name is taken from how this executable was invoked (its
    own file name), so `denoise.exe args...` behaves like `tools denoise
    args...`. Register one `[project.scripts]` entry per Processor name in
    pyproject.toml, all pointing to this same function.
    """
    command_name = PureWindowsPath(sys.argv[0]).stem
    command_name = _ENTRY_POINT_ALIASES.get(command_name, command_name)
    return main([command_name, *sys.argv[1:]])


if __name__ == "__main__":
    sys.exit(main())
