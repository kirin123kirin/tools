from pathlib import Path

import pytest

from workpytools.common.walk import Entry, compute_total_sizes, dedupe_by_fullpath, walk


def _make_tree(tmp_path: Path) -> Path:
    root = tmp_path / "root"
    root.mkdir()
    (root / "a.txt").write_text("hello")
    sub = root / "sub"
    sub.mkdir()
    (sub / "b.txt").write_text("world!!!!!")
    nested = sub / "nested"
    nested.mkdir()
    (nested / "c.txt").write_text("x" * 20)
    return root


# --- walk ---


def test_walk_finds_files_and_dirs(tmp_path: Path) -> None:
    root = _make_tree(tmp_path)
    entries, skipped = walk(str(root), source_label=str(root))

    types = {e.type for e in entries}
    assert types == {"file", "dir"}
    assert skipped == 0


def test_walk_recurses_into_subdirectories(tmp_path: Path) -> None:
    root = _make_tree(tmp_path)
    entries, _ = walk(str(root), source_label=str(root))

    names = {e.name for e in entries}
    assert names == {"a.txt", "sub", "b.txt", "nested", "c.txt"}


def test_walk_depth_relative_to_root(tmp_path: Path) -> None:
    root = _make_tree(tmp_path)
    entries, _ = walk(str(root), source_label=str(root))

    depth_by_name = {e.name: e.depth for e in entries}
    assert depth_by_name["a.txt"] == 1
    assert depth_by_name["sub"] == 1
    assert depth_by_name["b.txt"] == 2
    assert depth_by_name["nested"] == 2
    assert depth_by_name["c.txt"] == 3


def test_walk_excludes_named_directories(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / ".git").mkdir()
    (root / ".git" / "config").write_text("x")
    (root / "keep.txt").write_text("x")

    entries, _ = walk(str(root), source_label=str(root), exclude=frozenset({".git"}))

    names = {e.name for e in entries}
    assert "keep.txt" in names
    assert ".git" not in names
    assert "config" not in names


def test_walk_excludes_temp_files_by_default(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "~$locked.xlsx").write_text("x")
    (root / "normal.txt").write_text("x")

    entries, _ = walk(str(root), source_label=str(root))
    names = {e.name for e in entries}
    assert "normal.txt" in names
    assert "~$locked.xlsx" not in names


def test_walk_include_temp_option(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "~$locked.xlsx").write_text("x")

    entries, _ = walk(str(root), source_label=str(root), include_temp=True)
    names = {e.name for e in entries}
    assert "~$locked.xlsx" in names


def test_walk_inaccessible_dir_is_skipped_with_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "ok.txt").write_text("x")

    import os

    original_scandir = os.scandir
    call_count = {"n": 0}

    def fake_scandir(path):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return original_scandir(path)
        raise PermissionError("denied")

    (root / "blocked").mkdir()
    monkeypatch.setattr("workpytools.common.walk.os.scandir", fake_scandir)

    with caplog.at_level("WARNING"):
        entries, skipped = walk(str(root), source_label=str(root))

    assert skipped == 1
    assert "スキップ" in caplog.text


def test_empty_directory_returns_no_entries(tmp_path: Path) -> None:
    root = tmp_path / "empty"
    root.mkdir()
    entries, skipped = walk(str(root), source_label=str(root))
    assert entries == []
    assert skipped == 0


def test_source_label_attached_to_entries(tmp_path: Path) -> None:
    root = _make_tree(tmp_path)
    entries, _ = walk(str(root), source_label="mylabel")
    assert all(e.source == "mylabel" for e in entries)


def test_ext_empty_for_directories_and_extensionless_files(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "noext").write_text("x")
    (root / "sub").mkdir()

    entries, _ = walk(str(root), source_label=str(root))
    ext_by_name = {e.name: e.ext for e in entries}
    assert ext_by_name["noext"] == ""
    assert ext_by_name["sub"] == ""


def test_dir_size_is_none(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "sub").mkdir()

    entries, _ = walk(str(root), source_label=str(root))
    assert entries[0].size is None


def test_file_size_matches_actual_bytes(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "f.txt").write_bytes(b"x" * 42)

    entries, _ = walk(str(root), source_label=str(root))
    assert entries[0].size == 42


def test_does_not_recursionerror_on_many_stack_frames(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 明示スタック方式のため、Python既定の再帰上限(1000)を超える件数を
    # スタックに積んでも RecursionError にならないことを確認する。
    # 実ディレクトリではWindowsのMAX_PATH制限にすぐ当たってしまうため、
    # os.scandirの結果を差し替えて仮想的な深さ1200階層のツリーを模擬する。
    import sys

    from workpytools.common import walk as walk_module

    depth_limit = 1200
    assert depth_limit > sys.getrecursionlimit()

    class FakeDirEntry:
        def __init__(self, path: str, depth: int) -> None:
            self.name = f"d{depth}"
            self.path = path
            self._depth = depth

        def is_dir(self, follow_symlinks: bool = True) -> bool:
            return self._depth < depth_limit

        def stat(self, follow_symlinks: bool = True):
            class FakeStat:
                st_size = 0
                st_mtime = 0

            return FakeStat()

    class FakeScandirResult:
        def __init__(self, entries: list) -> None:
            self._entries = entries

        def __enter__(self):
            return self._entries

        def __exit__(self, *exc):
            return False

    def fake_scandir(path: str):
        depth = path.count("\\") if "\\" in path else path.count("/")
        return FakeScandirResult([FakeDirEntry(f"{path}/d{depth + 1}", depth + 1)])

    monkeypatch.setattr(walk_module.os, "scandir", fake_scandir)

    entries, skipped = walk("root", source_label="root")
    assert skipped == 0
    assert max(e.depth for e in entries) == depth_limit


# --- dedupe_by_fullpath ---


def test_dedupe_removes_duplicate_fullpaths() -> None:
    a = Entry("file", "x", "C:/a/x", "C:/a", ".txt", 1, "", 1, "s")
    b = Entry("file", "x", "C:/a/x", "C:/a", ".txt", 1, "", 1, "s2")
    result, skipped = dedupe_by_fullpath([a, b])
    assert len(result) == 1
    assert skipped == 1


def test_dedupe_case_insensitive_on_windows_paths() -> None:
    a = Entry("file", "x", "C:/Work/x", "C:/Work", ".txt", 1, "", 1, "s")
    b = Entry("file", "x", "C:/work/x", "C:/work", ".txt", 1, "", 1, "s")
    result, skipped = dedupe_by_fullpath([a, b])
    assert len(result) == 1
    assert skipped == 1


def test_dedupe_keeps_distinct_paths() -> None:
    a = Entry("file", "x", "C:/a/x", "C:/a", ".txt", 1, "", 1, "s")
    b = Entry("file", "y", "C:/a/y", "C:/a", ".txt", 1, "", 1, "s")
    result, skipped = dedupe_by_fullpath([a, b])
    assert len(result) == 2
    assert skipped == 0


# --- compute_total_sizes ---


def test_total_size_leaf_directory() -> None:
    entries = [
        Entry("file", "a.txt", "root/sub/a.txt", "root/sub", ".txt", 100, "", 2, "s"),
    ]
    totals = compute_total_sizes(entries)
    assert totals["root/sub"] == 100


def test_total_size_propagates_to_ancestors() -> None:
    entries = [
        Entry("file", "a.txt", "root/a.txt", "root", ".txt", 100, "", 1, "s"),
        Entry("dir", "sub", "root/sub", "root", "", None, "", 1, "s"),
        Entry("file", "b.txt", "root/sub/b.txt", "root/sub", ".txt", 200, "", 2, "s"),
        Entry("dir", "subsub", "root/sub/subsub", "root/sub", "", None, "", 2, "s"),
        Entry("file", "c.txt", "root/sub/subsub/c.txt", "root/sub/subsub", ".txt", 50, "", 3, "s"),
    ]
    totals = compute_total_sizes(entries)
    assert totals["root/sub/subsub"] == 50
    assert totals["root/sub"] == 250
    assert totals["root"] == 350


def test_total_size_empty_directory_is_zero() -> None:
    entries = [
        Entry("dir", "empty", "root/empty", "root", "", None, "", 1, "s"),
    ]
    totals = compute_total_sizes(entries)
    assert totals.get("root/empty", 0) == 0
