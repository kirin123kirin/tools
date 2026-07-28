"""Regenerate doc/help.html from every registered Processor's argparse help.

Run manually with `python scripts/gen_help.py`, or via the pre-commit hook
(scripts/pre-commit) which runs this automatically and re-stages the file.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from workpytools.common.help_gen import collect_command_help, render_help_html  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parent.parent
# doc/help.html: リポジトリ上でそのまま開いて見るための開発用コピー。
# src/workpytools/data/help.html: pip installでもtoolh.exeが開けるよう、
# パッケージデータとして同梱する実行時用コピー（package-dataに登録済み）。
_OUTPUT_PATHS = [
    _REPO_ROOT / "doc" / "help.html",
    _REPO_ROOT / "src" / "workpytools" / "data" / "help.html",
]


def main() -> int:
    commands = collect_command_help()
    html = render_help_html(commands)
    for path in _OUTPUT_PATHS:
        path.write_text(html, encoding="utf-8")
        print(f"generated: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
