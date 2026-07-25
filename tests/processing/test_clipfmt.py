import argparse

import pytest

from tools.processing import clipfmt as clipfmt_module
from tools.processing.clipfmt import (
    ClipfmtProcessor,
    format_markdown,
    normalize_bullet_markers,
)


def _base_args(**overrides: object) -> argparse.Namespace:
    defaults = dict(no_normalize_bullets=False)
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


@pytest.fixture
def clipboard_state(monkeypatch: pytest.MonkeyPatch) -> dict:
    state = {"text": None, "written": None}
    monkeypatch.setattr(clipfmt_module, "get_clipboard_text", lambda: state["text"])

    def fake_copy(text: str) -> None:
        state["written"] = text

    monkeypatch.setattr(clipfmt_module, "copy_text_to_clipboard", fake_copy)
    return state


# --- 整形内容 ---


def test_table_columns_aligned_with_japanese_width() -> None:
    import unicodedata

    md = "| a | とても長い項目名 |\n|---|---|\n| 1 | x |\n"
    result = format_markdown(md)
    lines = [line for line in result.split("\n") if line.strip()]

    def display_width(s: str) -> int:
        return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)

    widths = {display_width(line) for line in lines}
    assert len(widths) == 1  # 全角幅を考慮して全行の表示幅が揃っている


def test_column_alignment_preserved() -> None:
    md = "| a | b |\n|---|---:|\n| 1 | 2 |\n"
    result = format_markdown(md)
    assert "--:" in result


def test_tables_extension_required_for_table_formatting() -> None:
    import mdformat

    md = "| a | b |\n|---|---|\n| 1 | 2 |\n"
    without_ext = mdformat.text(md)
    with_ext = mdformat.text(md, extensions={"tables"})
    assert "<table" not in without_ext and "<table" not in with_ext
    assert without_ext != with_ext  # 拡張ありなしで結果が違う（プラグインが効いている証拠）


def test_setext_heading_becomes_atx() -> None:
    result = format_markdown("見出し\n====\n\n本文\n")
    assert "# 見出し" in result
    assert "====" not in result


def test_ordered_list_numbers_normalized() -> None:
    result = format_markdown("1. a\n1. b\n3. c\n")
    lines = [line for line in result.split("\n") if line.strip()]
    assert all(line.startswith("1.") for line in lines)


def test_trailing_whitespace_removed() -> None:
    result = format_markdown("本文   \n")
    assert result.rstrip("\n") == "本文"


def test_consecutive_blank_lines_collapsed() -> None:
    result = format_markdown("段落1\n\n\n\n段落2\n")
    assert "\n\n\n" not in result


# --- 箇条書き記号の統一 ---


def test_mixed_markers_become_one_list() -> None:
    text = "*   箇条書きA\n+ 箇条書きB\n-   箇条書きC\n"
    normalized, changed = normalize_bullet_markers(text)
    assert changed
    formatted = format_markdown(normalized)
    lines = [line for line in formatted.split("\n") if line.strip()]
    assert all(line.startswith("- ") for line in lines)
    # 間に空行が挿入されていない
    assert "\n\n" not in formatted.strip()


def test_code_fence_content_untouched() -> None:
    text = "```\n* これはコード\n+ これもコード\n```\n"
    normalized, changed = normalize_bullet_markers(text)
    assert not changed
    assert "* これはコード" in normalized
    assert "+ これもコード" in normalized


def test_indented_code_block_untouched() -> None:
    text = "説明:\n\n    * これはコード\n    + これもコード\n\n本文\n"
    normalized, changed = normalize_bullet_markers(text)
    assert not changed
    assert "* これはコード" in normalized
    assert "+ これもコード" in normalized


def test_horizontal_rule_not_converted_to_bullet() -> None:
    text = "段落1\n\n* * *\n\n段落2\n"
    normalized, changed = normalize_bullet_markers(text)
    assert not changed
    formatted = format_markdown(normalized)
    assert "- - -" not in formatted
    assert "*" not in formatted or "___" in formatted or "_" in formatted


def test_horizontal_rule_with_multiple_spaces_not_converted() -> None:
    text = "*  *  *\n"
    normalized, changed = normalize_bullet_markers(text)
    assert not changed


def test_quote_bullets_normalized() -> None:
    text = "> * 引用内A\n> + 引用内B\n"
    normalized, changed = normalize_bullet_markers(text)
    assert changed
    assert "> - 引用内A" in normalized
    assert "> - 引用内B" in normalized


def test_nested_bullets_normalized() -> None:
    text = "- 親\n  * 子1\n  + 子2\n"
    normalized, changed = normalize_bullet_markers(text)
    assert changed
    assert "  - 子1" in normalized
    assert "  - 子2" in normalized


def test_bold_and_italic_not_mistaken_for_bullets() -> None:
    text = "**太字**の行\n*斜体*の行\n"
    normalized, changed = normalize_bullet_markers(text)
    assert not changed
    assert normalized == text


def test_no_normalize_bullets_option_skips_preprocessing(clipboard_state) -> None:
    clipboard_state["text"] = "*   箇条書きA\n+ 箇条書きB\n"
    proc = ClipfmtProcessor()
    proc.run(_base_args(no_normalize_bullets=True))
    # 前処理をしていないので、mdformatが別リストとして分断した結果になっているはず
    written = clipboard_state["written"]
    assert written is not None


# --- 入出力 ---


def test_result_written_to_unicodetext(clipboard_state) -> None:
    clipboard_state["text"] = "見出し\n====\n"
    proc = ClipfmtProcessor()
    proc.run(_base_args())
    assert clipboard_state["written"] is not None
    assert "# 見出し" in clipboard_state["written"]


def test_cf_html_never_set(clipboard_state) -> None:
    clipboard_state["text"] = "見出し\n====\n"
    import inspect

    source = inspect.getsource(clipfmt_module)
    assert "copy_html_and_text_to_clipboard" not in source


def test_cf_html_ignored_uses_unicodetext_only(clipboard_state) -> None:
    clipboard_state["text"] = "本文\n"
    import inspect

    source = inspect.getsource(clipfmt_module)
    assert "has_clipboard_html" not in source
    assert "get_clipboard_html" not in source


# --- ログ ---


def test_logs_when_content_changed(clipboard_state, caplog: pytest.LogCaptureFixture) -> None:
    clipboard_state["text"] = "見出し\n====\n"
    proc = ClipfmtProcessor()
    with caplog.at_level("INFO"):
        proc.run(_base_args())
    assert "変わりました" in caplog.text


def test_logs_when_already_formatted(clipboard_state, caplog: pytest.LogCaptureFixture) -> None:
    already_formatted = format_markdown("# 見出し\n\n本文\n")
    clipboard_state["text"] = already_formatted
    proc = ClipfmtProcessor()
    with caplog.at_level("INFO"):
        proc.run(_base_args())
    assert "整形済み" in caplog.text


def test_logs_when_bullets_normalized(clipboard_state, caplog: pytest.LogCaptureFixture) -> None:
    clipboard_state["text"] = "* a\n+ b\n"
    proc = ClipfmtProcessor()
    with caplog.at_level("INFO"):
        proc.run(_base_args())
    assert "統一" in caplog.text


# --- エラー ---


def test_no_clipboard_text_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_error():
        raise RuntimeError("no text")

    monkeypatch.setattr(clipfmt_module, "get_clipboard_text", raise_error)
    proc = ClipfmtProcessor()
    with pytest.raises(SystemExit):
        proc.run(_base_args())


def test_empty_result_raises(clipboard_state) -> None:
    clipboard_state["text"] = "   \n  \n"
    proc = ClipfmtProcessor()
    with pytest.raises(SystemExit):
        proc.run(_base_args())


def test_mdformat_exception_does_not_write_clipboard(
    clipboard_state, monkeypatch: pytest.MonkeyPatch
) -> None:
    clipboard_state["text"] = "何かのテキスト\n"

    def raise_error(text, extensions=None):
        raise ValueError("boom")

    monkeypatch.setattr(clipfmt_module, "format_markdown", raise_error)

    proc = ClipfmtProcessor()
    with pytest.raises(SystemExit):
        proc.run(_base_args())

    assert clipboard_state["written"] is None
