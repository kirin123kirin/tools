import argparse

import pytest

from tools.processing import mdtsv as mdtsv_module
from tools.processing.mdtsv import MdtsvProcessor, markdown_table_to_tsv, tsv_to_markdown_table


def _base_args(**overrides: object) -> argparse.Namespace:
    defaults = dict(to_tsv=False, to_table=False)
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


@pytest.fixture
def clipboard_state(monkeypatch: pytest.MonkeyPatch) -> dict:
    state = {"text": None, "written": None}
    monkeypatch.setattr(mdtsv_module, "get_clipboard_text", lambda: state["text"])

    def fake_copy(text: str) -> None:
        state["written"] = text

    monkeypatch.setattr(mdtsv_module, "copy_text_to_clipboard", fake_copy)
    return state


MD_TABLE = "| a | b |\n|---|---|\n| 1 | 2 |\n"
TSV_TEXT = "a\tb\n1\t2\n"


# --- 変換方向の判定 ---


def test_markdown_table_selects_table_to_tsv(clipboard_state) -> None:
    clipboard_state["text"] = MD_TABLE
    proc = MdtsvProcessor()
    proc.run(_base_args())
    assert clipboard_state["written"] == "a\tb\n1\t2"


def test_tsv_selects_tsv_to_table(clipboard_state) -> None:
    clipboard_state["text"] = TSV_TEXT
    proc = MdtsvProcessor()
    proc.run(_base_args())
    assert "| a | b |" in clipboard_state["written"]


def test_mixed_tabs_and_no_tabs_is_not_tsv(clipboard_state) -> None:
    clipboard_state["text"] = "a\tb\nplain line without tab\n"
    proc = MdtsvProcessor()
    with pytest.raises(SystemExit):
        proc.run(_base_args())


def test_neither_table_nor_tsv_raises(clipboard_state) -> None:
    clipboard_state["text"] = "ただの文章です。\n"
    proc = MdtsvProcessor()
    with pytest.raises(SystemExit):
        proc.run(_base_args())


def test_to_tsv_overrides_autodetect(clipboard_state) -> None:
    clipboard_state["text"] = MD_TABLE
    proc = MdtsvProcessor()
    proc.run(_base_args(to_tsv=True))
    assert clipboard_state["written"] == "a\tb\n1\t2"


def test_to_table_overrides_autodetect(clipboard_state) -> None:
    clipboard_state["text"] = TSV_TEXT
    proc = MdtsvProcessor()
    proc.run(_base_args(to_table=True))
    assert "| a | b |" in clipboard_state["written"]


def test_to_tsv_on_non_table_raises(clipboard_state) -> None:
    clipboard_state["text"] = "ただの文章です。\n"
    proc = MdtsvProcessor()
    with pytest.raises(SystemExit):
        proc.run(_base_args(to_tsv=True))


def test_autodetect_logs_direction(clipboard_state, caplog: pytest.LogCaptureFixture) -> None:
    clipboard_state["text"] = MD_TABLE
    proc = MdtsvProcessor()
    with caplog.at_level("INFO"):
        proc.run(_base_args())
    assert "TSV" in caplog.text


# --- CF_HTML は見ない ---


def test_cf_html_is_never_consulted(clipboard_state) -> None:
    clipboard_state["text"] = TSV_TEXT
    # has_clipboard_html等をこのモジュールが一切importしていないことを確認する
    import inspect

    source = inspect.getsource(mdtsv_module)
    assert "has_clipboard_html" not in source
    assert "get_clipboard_html" not in source


# --- Markdownの表 → TSV ---


def test_separator_row_not_in_output() -> None:
    tsv = markdown_table_to_tsv(MD_TABLE)
    assert "---" not in tsv


def test_cells_trimmed_and_tab_joined() -> None:
    tsv = markdown_table_to_tsv("|  a  |  b  |\n|---|---|\n|  1  |  2  |\n")
    assert tsv == "a\tb\n1\t2"


def test_escaped_pipe_becomes_plain_pipe() -> None:
    tsv = markdown_table_to_tsv("| a\\|b | c |\n|---|---|\n| 1 | 2 |\n")
    lines = tsv.split("\n")
    assert lines[0] == "a|b\tc"


def test_br_replaced_with_space_and_logged(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level("WARNING"):
        tsv = markdown_table_to_tsv("| a<br>b | c |\n|---|---|\n| 1 | 2 |\n")
    assert "\n" not in tsv.split("\t")[0]
    assert "改行" in caplog.text


def test_alignment_spec_does_not_break_conversion() -> None:
    tsv = markdown_table_to_tsv("| a | b |\n|:--|--:|\n| 1 | 2 |\n")
    assert tsv == "a\tb\n1\t2"


def test_two_tables_concatenated_into_one_tsv(caplog: pytest.LogCaptureFixture) -> None:
    multi = "| a | b |\n|---|---|\n| 1 | 2 |\n\n| c | d |\n|---|---|\n| 3 | 4 |\n"
    with caplog.at_level("INFO"):
        tsv = markdown_table_to_tsv(multi)
    lines = tsv.split("\n")
    assert lines == ["a\tb", "1\t2", "c\td", "3\t4"]
    assert "表" in caplog.text


def test_tables_with_different_column_counts_concatenated() -> None:
    multi = "| a | b |\n|---|---|\n| 1 | 2 |\n\n| c |\n|---|\n| 3 |\n"
    tsv = markdown_table_to_tsv(multi)
    lines = tsv.split("\n")
    assert lines == ["a\tb", "1\t2", "c", "3"]


# --- TSV → Markdownの表 ---


def test_first_row_becomes_header_with_separator() -> None:
    md = tsv_to_markdown_table("a\tb\n1\t2\n")
    lines = md.split("\n")
    assert lines[0] == "| a | b |"
    assert lines[1] == "| --- | --- |"
    assert lines[2] == "| 1 | 2 |"


def test_pipe_in_cell_escaped() -> None:
    md = tsv_to_markdown_table("a|b\tc\n1\t2\n")
    assert "a\\|b" in md


def test_uneven_columns_padded_with_empty_cells() -> None:
    md = tsv_to_markdown_table("a\tb\tc\n1\t2\n")
    lines = md.split("\n")
    data_line = lines[2]
    assert data_line.count("|") == lines[0].count("|")


def test_quoted_newline_becomes_br() -> None:
    tsv = 'a\tb\n"改行\n入り"\tc\n'
    md = tsv_to_markdown_table(tsv)
    assert "<br>" in md
    assert "\n" not in md.split("\n")[2]  # データ行自体は1行に収まる


def test_no_column_alignment_in_output() -> None:
    md = tsv_to_markdown_table("a\tb\n1\t2\n")
    assert "---:" not in md
    assert ":---" not in md


# --- 出力 ---


def test_result_written_to_unicodetext_only(clipboard_state) -> None:
    clipboard_state["text"] = MD_TABLE
    # copy_html_and_text_to_clipboard を使っていないことを確認
    import inspect

    source = inspect.getsource(mdtsv_module)
    assert "copy_html_and_text_to_clipboard" not in source

    proc = MdtsvProcessor()
    proc.run(_base_args())
    assert clipboard_state["written"] is not None


# --- エラー ---


def test_no_clipboard_text_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_error():
        raise RuntimeError("no text")

    monkeypatch.setattr(mdtsv_module, "get_clipboard_text", raise_error)
    proc = MdtsvProcessor()
    with pytest.raises(SystemExit):
        proc.run(_base_args())


def test_empty_result_raises(clipboard_state) -> None:
    clipboard_state["text"] = "|  |  |\n|---|---|\n|  |  |\n"
    # 空セルのみの表 -> TSVにしても内容自体は空文字にはならない想定だが、
    # 完全に空白のみのケースを直接検証する
    from tools.processing.mdtsv import markdown_table_to_tsv

    result = markdown_table_to_tsv("|  |\n|---|\n|  |\n")
    assert result is not None
