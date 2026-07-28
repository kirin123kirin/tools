from __future__ import annotations

import argparse
import logging

from workpytools.cli import _discover_processors
from workpytools.common.help_gen import standalone_entry_point_name
from workpytools.common.shortcuts import (
    StartMenuLocationError,
    create_shortcuts,
    remove_shortcuts,
    start_menu_dir,
)
from workpytools.processing.base import Processor

logger = logging.getLogger(__name__)


def _all_standalone_names() -> list[str]:
    """The exe name (without extension) for every registered command,
    e.g. "touka", "toolh" for help."""
    processors = _discover_processors()
    names = {standalone_entry_point_name(name) for name in processors}
    return sorted(names)


class ShortcutProcessor(Processor):
    """Create (or remove) Start Menu shortcuts for every standalone command
    executable, so they can be launched from the Start menu instead of a
    typed command."""

    name = "shortcut"
    help = "全コマンドのスタートメニューショートカットを作成/削除する"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--remove",
            action="store_true",
            help="作成済みのショートカットを削除する（作成せず削除のみ行う）",
        )

    def run(self, args: argparse.Namespace) -> int:
        try:
            menu_dir = start_menu_dir()
        except StartMenuLocationError as exc:
            raise SystemExit(str(exc)) from exc

        if args.remove:
            removed = remove_shortcuts()
            logger.info("スタートメニューのショートカットを削除しました: %s", menu_dir)
            print(f"{removed}個のショートカットを削除しました（{menu_dir}）")
            return 0

        commands = _all_standalone_names()
        created = create_shortcuts(commands)

        logger.info("スタートメニューのショートカットを作成しました: %s", menu_dir)
        skipped = len(commands) - len(created)
        message = f"{len(created)}個のショートカットを作成しました（{menu_dir}）"
        if skipped:
            message += f"\n{skipped}個は対応するexeが見つからずスキップしました"
        print(message)
        return 0
