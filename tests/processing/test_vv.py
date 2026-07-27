import argparse
from pathlib import Path

import pytest

from workpytools.common.textfile import display_width
from workpytools.processing import vv as vv_module
from workpytools.processing.vv import VvProcessor, format_prompt_list, list_prompts


def _base_args(**overrides: object) -> argparse.Namespace:
    defaults = dict(number=None)
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


@pytest.fixture
def prompts_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    directory = tmp_path / "vv"
    directory.mkdir()
    monkeypatch.setattr(vv_module, "vv_prompts_dir", lambda: directory)
    return directory


@pytest.fixture
def clipboard_writes(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    writes: list[str] = []
    monkeypatch.setattr(vv_module, "copy_text_to_clipboard", lambda text: writes.append(text))
    return writes


def _write(directory: Path, name: str, body: str) -> Path:
    path = directory / name
    path.write_text(body, encoding="utf-8")
    return path


# --- 一覧表示 ---


def test_lists_txt_files_sorted_by_name(prompts_dir, clipboard_writes, capsys) -> None:
    _write(prompts_dir, "b.txt", "B本文")
    _write(prompts_dir, "a.txt", "A本文")

    VvProcessor().run(_base_args())

    out = capsys.readouterr().out
    lines = [line for line in out.split("\n") if line.strip()]
    assert lines[0].startswith("1: a")
    assert lines[1].startswith("2: b")


def test_listing_never_touches_clipboard(prompts_dir, clipboard_writes, capsys) -> None:
    _write(prompts_dir, "a.txt", "本文")

    VvProcessor().run(_base_args())

    assert clipboard_writes == []


def test_txt_extension_hidden_in_listing(prompts_dir, clipboard_writes, capsys) -> None:
    _write(prompts_dir, "企画書.txt", "本文")

    VvProcessor().run(_base_args())

    out = capsys.readouterr().out
    assert "企画書" in out
    assert ".txt" not in out


def test_missing_directory_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(vv_module, "vv_prompts_dir", lambda: tmp_path / "does_not_exist")
    with pytest.raises(SystemExit):
        VvProcessor().run(_base_args())


def test_empty_directory_raises(prompts_dir) -> None:
    with pytest.raises(SystemExit):
        VvProcessor().run(_base_args())


def test_numbers_right_aligned_with_ten_or_more(prompts_dir, clipboard_writes, capsys) -> None:
    for i in range(1, 13):
        _write(prompts_dir, f"{i:02d}_p.txt", "本文")

    VvProcessor().run(_base_args())

    lines = [line for line in capsys.readouterr().out.split("\n") if line.strip()]
    # 1桁の番号は右寄せで先頭に空白が入る
    assert lines[0].startswith(" 1:")
    assert lines[11].startswith("12:")


def test_preview_shown_for_each_entry(prompts_dir, clipboard_writes, capsys) -> None:
    _write(prompts_dir, "a.txt", "これは本文の冒頭です")

    VvProcessor().run(_base_args())

    assert "これは本文の冒頭です" in capsys.readouterr().out


def test_preview_uses_first_non_blank_line(prompts_dir, clipboard_writes, capsys) -> None:
    _write(prompts_dir, "a.txt", "\n\n  \n意味のある行\n")

    VvProcessor().run(_base_args())

    assert "意味のある行" in capsys.readouterr().out


def test_empty_file_shows_name_only(prompts_dir, clipboard_writes, capsys) -> None:
    _write(prompts_dir, "空.txt", "")

    VvProcessor().run(_base_args())

    lines = [line for line in capsys.readouterr().out.split("\n") if line.strip()]
    assert lines[0].strip() == "1: 空"


def test_long_preview_truncated_with_ellipsis(prompts_dir, clipboard_writes, capsys) -> None:
    _write(prompts_dir, "a.txt", "あ" * 200)

    VvProcessor().run(_base_args())

    out = capsys.readouterr().out
    assert "..." in out
    assert "あ" * 200 not in out


# --- 桁揃え（表示幅） ---


def test_preview_column_aligned_with_mixed_width_names(
    prompts_dir, clipboard_writes, capsys
) -> None:
    _write(prompts_dir, "1_企画書雛形.txt", "全角の名前")
    _write(prompts_dir, "2_AI_prompt.txt", "半角の名前")

    VvProcessor().run(_base_args())

    lines = [line for line in capsys.readouterr().out.split("\n") if line.strip()]
    # 各行のプレビュー開始位置（表示幅）が一致すること。
    # len()で揃える実装だと半角名の行だけ手前にずれる。
    starts = [display_width(line[: line.index("全角の名前" if "全角" in line else "半角の名前")])
              for line in lines]
    assert starts[0] == starts[1]


def test_truncation_uses_display_width_not_char_count() -> None:
    from workpytools.common.textfile import truncate_to_width

    fullwidth = truncate_to_width("あ" * 50, 20)
    halfwidth = truncate_to_width("a" * 50, 20)

    assert display_width(fullwidth) <= 20
    assert display_width(halfwidth) <= 20


# --- 対象ファイルと並び順 ---


def test_uppercase_extension_included(prompts_dir, clipboard_writes, capsys) -> None:
    _write(prompts_dir, "大文字.TXT", "本文")
    _write(prompts_dir, "混在.Txt", "本文")

    VvProcessor().run(_base_args())

    out = capsys.readouterr().out
    assert "大文字" in out
    assert "混在" in out


def test_non_txt_files_excluded(prompts_dir, clipboard_writes, capsys) -> None:
    _write(prompts_dir, "含む.txt", "本文")
    _write(prompts_dir, "除外.md", "本文")

    VvProcessor().run(_base_args())

    out = capsys.readouterr().out
    assert "含む" in out
    assert "除外" not in out


def test_sorted_regardless_of_iteration_order(
    prompts_dir, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = [_write(prompts_dir, name, "本文") for name in ("a.txt", "b.txt", "c.txt")]

    # iterdir が逆順を返しても、出力は昇順であること
    monkeypatch.setattr(Path, "iterdir", lambda self: iter(reversed(paths)))

    prompts = list_prompts(prompts_dir)
    assert [p.name for p in prompts] == ["a", "b", "c"]


def test_subfolder_txt_not_listed(prompts_dir, clipboard_writes, capsys) -> None:
    _write(prompts_dir, "直下.txt", "本文")
    sub = prompts_dir / "sub"
    sub.mkdir()
    _write(sub, "配下.txt", "本文")

    VvProcessor().run(_base_args())

    out = capsys.readouterr().out
    assert "直下" in out
    assert "配下" not in out


# --- 番号指定 ---


def test_valid_number_copies_body(prompts_dir, clipboard_writes, capsys) -> None:
    _write(prompts_dir, "a.txt", "コピーされる本文")

    VvProcessor().run(_base_args(number="1"))

    assert "コピーされる本文" in clipboard_writes[0]


def test_number_does_not_print_list(prompts_dir, clipboard_writes, capsys) -> None:
    _write(prompts_dir, "a.txt", "本文A")
    _write(prompts_dir, "b.txt", "本文B")

    VvProcessor().run(_base_args(number="1"))

    out = capsys.readouterr().out
    assert "2:" not in out


def test_number_prints_confirmation_with_name(prompts_dir, clipboard_writes, capsys) -> None:
    _write(prompts_dir, "企画書.txt", "本文")

    VvProcessor().run(_base_args(number="1"))

    assert "企画書" in capsys.readouterr().out


def test_boundary_first_and_last(prompts_dir, clipboard_writes) -> None:
    _write(prompts_dir, "a.txt", "最初")
    _write(prompts_dir, "b.txt", "中間")
    _write(prompts_dir, "c.txt", "最後")

    VvProcessor().run(_base_args(number="1"))
    VvProcessor().run(_base_args(number="3"))

    assert "最初" in clipboard_writes[0]
    assert "最後" in clipboard_writes[1]


@pytest.mark.parametrize("bad", ["0", "-1", "2"])
def test_out_of_range_numbers_raise(prompts_dir, bad: str) -> None:
    _write(prompts_dir, "a.txt", "本文")

    with pytest.raises(SystemExit) as exc:
        VvProcessor().run(_base_args(number=bad))

    assert "1〜1" in str(exc.value)


@pytest.mark.parametrize("bad", ["abc", "1.5", ""])
def test_non_numeric_arguments_raise_japanese_error(prompts_dir, bad: str) -> None:
    _write(prompts_dir, "a.txt", "本文")

    with pytest.raises(SystemExit) as exc:
        VvProcessor().run(_base_args(number=bad))

    assert "数値" in str(exc.value)


# --- ファイル読み込み ---


def test_utf8_with_and_without_bom(prompts_dir, clipboard_writes) -> None:
    (prompts_dir / "bom.txt").write_bytes(b"\xef\xbb\xbf" + "BOM付き".encode())
    (prompts_dir / "nobom.txt").write_text("BOMなし", encoding="utf-8")

    VvProcessor().run(_base_args(number="1"))
    VvProcessor().run(_base_args(number="2"))

    assert "BOM付き" in clipboard_writes[0]
    assert "BOMなし" in clipboard_writes[1]


def test_cp932_file_read_via_fallback(prompts_dir, clipboard_writes) -> None:
    (prompts_dir / "sjis.txt").write_bytes("シフトJISの本文".encode("cp932"))

    VvProcessor().run(_base_args(number="1"))

    assert "シフトJISの本文" in clipboard_writes[0]


def test_missing_appdata_raises_readable_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from workpytools.common.config import ConfigLocationError

    def raise_error():
        raise ConfigLocationError("環境変数 APPDATA が設定されていません")

    monkeypatch.setattr(vv_module, "vv_prompts_dir", raise_error)

    with pytest.raises(SystemExit) as exc:
        VvProcessor().run(_base_args())

    assert "APPDATA" in str(exc.value)


# --- 改行コード ---


def test_lf_file_copied_as_crlf(prompts_dir, clipboard_writes) -> None:
    (prompts_dir / "lf.txt").write_bytes("1行目\n2行目\n".encode())

    VvProcessor().run(_base_args(number="1"))

    assert clipboard_writes[0] == "1行目\r\n2行目\r\n"


def test_crlf_file_not_double_converted(prompts_dir, clipboard_writes) -> None:
    (prompts_dir / "crlf.txt").write_bytes("1行目\r\n2行目\r\n".encode())

    VvProcessor().run(_base_args(number="1"))

    assert "\r\r\n" not in clipboard_writes[0]
    assert clipboard_writes[0] == "1行目\r\n2行目\r\n"


def test_cr_and_mixed_newlines_normalized(prompts_dir, clipboard_writes) -> None:
    (prompts_dir / "mixed.txt").write_bytes(b"A\rB\nC\r\nD")

    VvProcessor().run(_base_args(number="1"))

    assert clipboard_writes[0] == "A\r\nB\r\nC\r\nD"


# --- 出力 ---


def test_only_unicodetext_is_set(prompts_dir) -> None:
    import inspect

    source = inspect.getsource(vv_module)
    assert "copy_html_and_text_to_clipboard" not in source
    assert "copy_text_to_clipboard" in source


# --- format_prompt_list 単体 ---


def test_unreadable_file_marked_in_listing(
    prompts_dir, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(prompts_dir, "a.txt", "本文")
    prompts = list_prompts(prompts_dir)

    def raise_oserror(path, encoding=None):
        raise OSError("permission denied")

    monkeypatch.setattr(vv_module, "read_text_with_fallback", raise_oserror)

    lines = format_prompt_list(prompts)
    assert "読み込めません" in lines[0]
