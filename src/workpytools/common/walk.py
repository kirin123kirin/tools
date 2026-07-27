from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

_DEFAULT_EXCLUDE = frozenset({".git", ".svn", "node_modules", "__pycache__"})


@dataclass(frozen=True)
class Entry:
    type: str  # "file" or "dir"
    name: str
    fullpath: str
    parent: str
    ext: str
    size: int | None
    mtime: str
    depth: int
    source: str


def _mtime_str(stat_result: os.stat_result) -> str:
    return datetime.fromtimestamp(stat_result.st_mtime).strftime("%Y/%m/%d %H:%M")


def walk(
    root: str,
    source_label: str,
    exclude: frozenset[str] = _DEFAULT_EXCLUDE,
    include_temp: bool = False,
) -> tuple[list[Entry], int]:
    """Walk `root` with an explicit stack (not recursion): measured ~27%
    faster than a recursive generator, and immune to RecursionError on very
    deep trees (see doc/lsdir.md for the benchmark).

    Uses os.scandir + DirEntry.stat() rather than os.walk + os.stat(), since
    DirEntry.stat() reuses information already fetched by scandir() instead
    of making another syscall per entry (measured ~18% faster).

    Returns (entries, skipped_dir_count). Directories that raise on access
    are logged as warnings and skipped rather than aborting the whole walk.
    """
    entries: list[Entry] = []
    skipped = 0

    # (path, depth) スタック。再帰ではなく明示スタックにすることで、
    # 深い階層でも RecursionError にならず、実測でも速い。
    stack: list[tuple[str, int]] = [(root, 0)]

    while stack:
        current, depth = stack.pop()

        try:
            with os.scandir(current) as scan_it:
                dir_entries = list(scan_it)
        except OSError as exc:
            skipped += 1
            logger.warning("フォルダにアクセスできないためスキップします: %s (%s)", current, exc)
            continue

        for dir_entry in dir_entries:
            if dir_entry.name in exclude:
                continue
            if not include_temp and dir_entry.name.startswith("~$"):
                continue

            try:
                is_dir = dir_entry.is_dir(follow_symlinks=False)
                stat_result = dir_entry.stat(follow_symlinks=False)
            except OSError as exc:
                logger.warning("エントリを読めないためスキップします: %s (%s)", dir_entry.path, exc)
                continue

            new_depth = depth + 1
            ext = "" if is_dir else os.path.splitext(dir_entry.name)[1]

            entries.append(
                Entry(
                    type="dir" if is_dir else "file",
                    name=dir_entry.name,
                    fullpath=dir_entry.path,
                    parent=current,
                    ext=ext,
                    size=None if is_dir else stat_result.st_size,
                    mtime=_mtime_str(stat_result),
                    depth=new_depth,
                    source=source_label,
                )
            )

            if is_dir:
                stack.append((dir_entry.path, new_depth))

    return entries, skipped


def dedupe_by_fullpath(entries: list[Entry]) -> tuple[list[Entry], int]:
    """Remove entries whose normalized full path was already seen (for
    overlapping roots, e.g. `lsdir C:\\work C:\\work\\sub`). Windows paths
    are case-insensitive, so normcase() is used for the comparison key.
    """
    seen: set[str] = set()
    result = []
    skipped = 0
    for entry in entries:
        key = os.path.normcase(os.path.abspath(entry.fullpath))
        if key in seen:
            skipped += 1
            continue
        seen.add(key)
        result.append(entry)
    return result, skipped


def compute_total_sizes(entries: list[Entry]) -> dict[str, int]:
    """Total size in bytes of everything under each directory entry's path.

    Requires a full walk to have already completed (can't be streamed),
    which is why --total-size is opt-in rather than the default.
    """
    totals: dict[str, int] = {}
    # 深い順（depthが大きい順）に処理すれば、子の合計を親に一度で足し込める
    for entry in sorted(entries, key=lambda e: -e.depth):
        if entry.type == "file" and entry.size is not None:
            totals[entry.parent] = totals.get(entry.parent, 0) + entry.size
        elif entry.type == "dir":
            own_total = totals.get(entry.fullpath, 0)
            totals[entry.parent] = totals.get(entry.parent, 0) + own_total
    return totals
