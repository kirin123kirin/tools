from __future__ import annotations

import argparse
import html as html_module
from dataclasses import dataclass

from tools.cli import _discover_processors
from tools.processing.base import Processor


@dataclass(frozen=True)
class CommandHelp:
    name: str
    summary: str
    usage: str
    full_help: str


def collect_command_help() -> list[CommandHelp]:
    """Build per-command help text by rendering each Processor's own argparse help."""
    processors = _discover_processors()
    results: list[CommandHelp] = []

    for name in sorted(processors):
        proc = processors[name]
        parser = _build_standalone_parser(proc)
        full_help = parser.format_help()
        results.append(
            CommandHelp(
                name=name,
                summary=proc.help,
                usage=parser.format_usage(),
                full_help=full_help,
            )
        )

    return results


def _build_standalone_parser(proc: Processor) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=proc.name, description=proc.help)
    proc.add_arguments(parser)
    return parser


def render_help_html(commands: list[CommandHelp]) -> str:
    rows = []
    for cmd in commands:
        rows.append(
            "<section class=\"command\">\n"
            f"<h2 id=\"{html_module.escape(cmd.name)}\">{html_module.escape(cmd.name)}</h2>\n"
            f"<p class=\"summary\">{html_module.escape(cmd.summary)}</p>\n"
            f"<pre>{html_module.escape(cmd.full_help)}</pre>\n"
            "</section>"
        )

    toc_items = "\n".join(
        f'<li><a href="#{html_module.escape(c.name)}">{html_module.escape(c.name)}</a>'
        f" — {html_module.escape(c.summary)}</li>"
        for c in commands
    )

    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta http-equiv="Cache-Control" content="no-store">
<title>tools コマンドヘルプ</title>
<style>
:root {{ color-scheme: light dark; }}
body {{
  max-width: 50rem;
  margin: 2rem auto;
  padding: 0 1rem;
  font-family: -apple-system, "Segoe UI", sans-serif;
  line-height: 1.6;
  color: #222;
  background: #fff;
}}
h1 {{ font-size: 1.6rem; }}
h2 {{
  font-size: 1.2rem;
  margin-top: 2rem;
  border-bottom: 1px solid #ccc;
  padding-bottom: 0.3rem;
}}
.summary {{ color: #555; margin: 0.3rem 0 0.8rem; }}
pre {{
  background: #f5f5f5;
  padding: 0.8rem;
  overflow-x: auto;
  font-family: Consolas, "Courier New", monospace;
  font-size: 0.85rem;
}}
nav ul {{ padding-left: 1.2rem; }}
nav a {{ text-decoration: none; }}
nav a:hover {{ text-decoration: underline; }}
@media (prefers-color-scheme: dark) {{
  body {{ color: #ddd; background: #1e1e1e; }}
  h2 {{ border-bottom-color: #555; }}
  .summary {{ color: #aaa; }}
  pre {{ background: #2a2a2a; }}
}}
</style>
</head>
<body>
<h1>tools コマンド一覧</h1>
<nav>
<ul>
{toc_items}
</ul>
</nav>
{chr(10).join(rows)}
</body>
</html>
"""
