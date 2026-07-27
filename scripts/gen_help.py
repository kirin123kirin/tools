"""Regenerate doc/help.html from every registered Processor's argparse help.

Run manually with `python scripts/gen_help.py`, or via the pre-commit hook
(scripts/pre-commit) which runs this automatically and re-stages the file.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from workpytools.common.help_gen import collect_command_help, render_help_html  # noqa: E402

_OUTPUT_PATH = Path(__file__).resolve().parent.parent / "doc" / "help.html"


def main() -> int:
    commands = collect_command_help()
    html = render_help_html(commands)
    _OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(f"generated: {_OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
