import argparse
from pathlib import Path

import pytest

from tools.processing import lsdir as lsdir_module
from tools.processing.lsdir import LsdirProcessor


def _base_args(**overrides: object) -> argparse.Namespace:
    defaults = dict(
        path=[],
        output=None,
        clip=False,
        files_only=False,
        dirs_only=False,
        exclude=list(lsdir_module._DEFAULT_EXCLUDE),
        include_temp=False,
        total_size=False,
        unit="kb",
        resolve_link=False,
        encoding="utf-8",
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


@pytest.fixture
def clipboard_state(monkeypatch: pytest.MonkeyPatch) -> dict:
    state = {"written": None}

    def fake_copy(text: str) -> None:
        state["written"] = text

    monkeypatch.setattr(lsdir_module, "copy_text_to_clipboard", fake_copy)
    return state


def _make_tree(tmp_path: Path) -> Path:
    root = tmp_path / "root"
    root.mkdir()
    (root / "a.txt").write_bytes(b"x" * 10)
    sub = root / "sub"
    sub.mkdir()
    (sub / "b.txt").write_bytes(b"x" * 2048)
    return root


# --- 走査 ---


def test_recurses_and_outputs_all_entries(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    root = _make_tree(tmp_path)

    LsdirProcessor().run(_base_args(path=[str(root)]))

    out = capsys.readouterr().out
    assert "a.txt" in out
    assert "b.txt" in out
    assert "sub" in out


def test_files_only_excludes_directories(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    root = _make_tree(tmp_path)

    LsdirProcessor().run(_base_args(path=[str(root)], files_only=True))

    out = capsys.readouterr().out
    lines = out.strip().split("\n")[1:]
    types = [line.split("\t")[1] for line in lines]
    assert set(types) == {"file"}


def test_dirs_only_excludes_files(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    root = _make_tree(tmp_path)

    LsdirProcessor().run(_base_args(path=[str(root)], dirs_only=True))

    out = capsys.readouterr().out
    lines = out.strip().split("\n")[1:]
    types = [line.split("\t")[1] for line in lines]
    assert set(types) == {"dir"}


def test_exclude_option_skips_named_directories(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "node_modules").mkdir()
    (root / "node_modules" / "pkg.json").write_text("x")
    (root / "keep.txt").write_text("x")

    LsdirProcessor().run(_base_args(path=[str(root)]))

    out = capsys.readouterr().out
    assert "node_modules" not in out
    assert "keep.txt" in out


def test_temp_files_excluded_by_default(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "~$locked.xlsx").write_text("x")
    (root / "normal.txt").write_text("x")

    LsdirProcessor().run(_base_args(path=[str(root)]))

    out = capsys.readouterr().out
    assert "~$locked.xlsx" not in out
    assert "normal.txt" in out


def test_include_temp_option(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "~$locked.xlsx").write_text("x")

    LsdirProcessor().run(_base_args(path=[str(root)], include_temp=True))

    out = capsys.readouterr().out
    assert "~$locked.xlsx" in out


def test_nonexistent_path_raises(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        LsdirProcessor().run(_base_args(path=[str(tmp_path / "missing")]))


def test_empty_directory_outputs_header_only(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    root = tmp_path / "empty"
    root.mkdir()

    result = LsdirProcessor().run(_base_args(path=[str(root)]))

    out = capsys.readouterr().out
    assert result == 0
    assert out.strip().split("\n")[0].startswith("source\t")
    assert len(out.strip().split("\n")) == 1


def test_duplicate_roots_deduped(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    root = _make_tree(tmp_path)

    LsdirProcessor().run(_base_args(path=[str(root), str(root / "sub")]))

    out = capsys.readouterr().out
    lines = out.strip().split("\n")[1:]
    fullpaths = [line.split("\t")[3] for line in lines]
    assert len(fullpaths) == len(set(fullpaths))


# --- 出力列 ---


def test_header_columns_fixed(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    root = _make_tree(tmp_path)

    LsdirProcessor().run(_base_args(path=[str(root)]))

    out = capsys.readouterr().out
    header = out.strip().split("\n")[0].split("\t")
    assert header == [
        "source",
        "type",
        "name",
        "fullpath",
        "parent",
        "ext",
        "size",
        "mtime",
        "depth",
    ]


def test_link_column_only_with_resolve_link(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    root = _make_tree(tmp_path)

    LsdirProcessor().run(_base_args(path=[str(root)]))
    out = capsys.readouterr().out
    assert "link" not in out.strip().split("\n")[0].split("\t")

    LsdirProcessor().run(_base_args(path=[str(root)], resolve_link=True))
    out = capsys.readouterr().out
    assert "link" in out.strip().split("\n")[0].split("\t")


def test_depth_column_present(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    root = _make_tree(tmp_path)

    LsdirProcessor().run(_base_args(path=[str(root)]))

    out = capsys.readouterr().out
    header = out.strip().split("\n")[0].split("\t")
    depth_idx = header.index("depth")
    lines = out.strip().split("\n")[1:]
    for line in lines:
        assert line.split("\t")[depth_idx].isdigit()


def test_dir_row_size_is_blank(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    root = _make_tree(tmp_path)

    LsdirProcessor().run(_base_args(path=[str(root)]))

    out = capsys.readouterr().out
    header = out.strip().split("\n")[0].split("\t")
    size_idx = header.index("size")
    type_idx = header.index("type")
    for line in out.strip().split("\n")[1:]:
        fields = line.split("\t")
        if fields[type_idx] == "dir":
            assert fields[size_idx] == ""


# --- サイズ単位 ---


def test_default_unit_is_kb_two_decimals(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "f.txt").write_bytes(b"x" * 1024)

    LsdirProcessor().run(_base_args(path=[str(root)]))

    out = capsys.readouterr().out
    line = [ln for ln in out.strip().split("\n") if "f.txt" in ln][0]
    header = out.strip().split("\n")[0].split("\t")
    size_idx = header.index("size")
    assert line.split("\t")[size_idx] == "1.00"


def test_unit_b_outputs_raw_bytes(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "f.txt").write_bytes(b"x" * 1024)

    LsdirProcessor().run(_base_args(path=[str(root)], unit="b"))

    out = capsys.readouterr().out
    line = [ln for ln in out.strip().split("\n") if "f.txt" in ln][0]
    header = out.strip().split("\n")[0].split("\t")
    size_idx = header.index("size")
    assert line.split("\t")[size_idx] == "1024"


def test_unit_mb(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "f.txt").write_bytes(b"x" * (1024 * 1024))

    LsdirProcessor().run(_base_args(path=[str(root)], unit="mb"))

    out = capsys.readouterr().out
    line = [ln for ln in out.strip().split("\n") if "f.txt" in ln][0]
    header = out.strip().split("\n")[0].split("\t")
    size_idx = header.index("size")
    assert line.split("\t")[size_idx] == "1.00"


# --- --total-size ---


def test_total_size_computes_directory_totals(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    root = _make_tree(tmp_path)

    LsdirProcessor().run(_base_args(path=[str(root)], total_size=True, unit="b"))

    out = capsys.readouterr().out
    header = out.strip().split("\n")[0].split("\t")
    size_idx = header.index("size")
    name_idx = header.index("name")
    for line in out.strip().split("\n")[1:]:
        fields = line.split("\t")
        if fields[name_idx] == "sub":
            assert fields[size_idx] == "2048"
        if fields[name_idx] == "root":
            assert fields[size_idx] == "2058"


def test_total_size_with_dirs_only_still_correct(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    # --dirs-onlyでファイル行を落としても、フィルタ前に合計計算しているので
    # サイズが0にならないことを確認する（実データ検証で見つかったバグの回帰テスト）
    root = _make_tree(tmp_path)

    LsdirProcessor().run(
        _base_args(path=[str(root)], total_size=True, unit="b", dirs_only=True)
    )

    out = capsys.readouterr().out
    header = out.strip().split("\n")[0].split("\t")
    size_idx = header.index("size")
    name_idx = header.index("name")
    lines = out.strip().split("\n")[1:]
    sub_line = [line for line in lines if line.split("\t")[name_idx] == "sub"][0]
    assert sub_line.split("\t")[size_idx] == "2048"


def test_total_size_empty_directory_is_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "empty_sub").mkdir()

    LsdirProcessor().run(_base_args(path=[str(root)], total_size=True, unit="b"))

    out = capsys.readouterr().out
    header = out.strip().split("\n")[0].split("\t")
    size_idx = header.index("size")
    name_idx = header.index("name")
    lines = out.strip().split("\n")[1:]
    sub_line = [line for line in lines if line.split("\t")[name_idx] == "empty_sub"][0]
    assert sub_line.split("\t")[size_idx] == "0"


# --- .lnk解決 ---


def test_resolve_link_uses_wscript_shell(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "shortcut.lnk").write_text("dummy")

    class FakeShortcut:
        TargetPath = r"C:\resolved\target.txt"

    class FakeShell:
        def CreateShortCut(self, path):
            return FakeShortcut()

    class FakeWin32Com:
        class client:
            @staticmethod
            def Dispatch(name):
                assert name == "WScript.Shell"
                return FakeShell()

    import sys

    monkeypatch.setitem(sys.modules, "win32com.client", FakeWin32Com.client)
    monkeypatch.setitem(sys.modules, "win32com", FakeWin32Com)

    LsdirProcessor().run(_base_args(path=[str(root)], resolve_link=True))

    out = capsys.readouterr().out
    assert r"C:\resolved\target.txt" in out


def test_resolve_link_failure_logs_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "broken.lnk").write_text("dummy")

    class FakeShell:
        def CreateShortCut(self, path):
            raise RuntimeError("boom")

    class FakeWin32Com:
        class client:
            @staticmethod
            def Dispatch(name):
                return FakeShell()

    import sys

    monkeypatch.setitem(sys.modules, "win32com.client", FakeWin32Com.client)
    monkeypatch.setitem(sys.modules, "win32com", FakeWin32Com)

    with caplog.at_level("WARNING"):
        LsdirProcessor().run(_base_args(path=[str(root)], resolve_link=True))

    assert "失敗" in caplog.text


# --- 出力形式 ---


def test_default_output_is_tsv_stdout(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    root = _make_tree(tmp_path)

    LsdirProcessor().run(_base_args(path=[str(root)]))

    out = capsys.readouterr().out
    assert "\t" in out.split("\n")[0]


def test_output_xlsx_file(tmp_path: Path) -> None:
    root = _make_tree(tmp_path)
    out_path = tmp_path / "result.xlsx"

    LsdirProcessor().run(_base_args(path=[str(root)], output=str(out_path)))

    assert out_path.exists()

    import openpyxl

    wb = openpyxl.load_workbook(out_path)
    rows = list(wb.active.iter_rows(values_only=True))
    assert rows[0][0] == "source"


def test_output_tsv_file(tmp_path: Path) -> None:
    root = _make_tree(tmp_path)
    out_path = tmp_path / "result.tsv"

    LsdirProcessor().run(_base_args(path=[str(root)], output=str(out_path)))

    assert out_path.exists()
    assert "source" in out_path.read_text(encoding="cp932")


def test_clip_option_copies_and_suppresses_stdout(
    tmp_path: Path, clipboard_state, capsys: pytest.CaptureFixture
) -> None:
    root = _make_tree(tmp_path)

    LsdirProcessor().run(_base_args(path=[str(root)], clip=True))

    out = capsys.readouterr().out
    assert clipboard_state["written"] is not None
    assert "source\t" not in out
    assert "コピー" in out


def test_header_only_once_across_multiple_roots(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    root1 = tmp_path / "r1"
    root1.mkdir()
    (root1 / "a.txt").write_text("x")
    root2 = tmp_path / "r2"
    root2.mkdir()
    (root2 / "b.txt").write_text("x")

    LsdirProcessor().run(_base_args(path=[str(root1), str(root2)]))

    out = capsys.readouterr().out
    assert out.count("source\t") == 1
