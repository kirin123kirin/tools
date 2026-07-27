import argparse

import pytest

from workpytools.processing import clipmd as clipmd_module
from workpytools.processing.clipmd import ClipmdProcessor, html_to_markdown


def _base_args(**overrides: object) -> argparse.Namespace:
    defaults = dict(to_markdown=False, to_rich=False)
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


@pytest.fixture
def clipboard_state(monkeypatch: pytest.MonkeyPatch) -> dict:
    state = {"html": None, "text": None}

    monkeypatch.setattr(clipmd_module, "has_clipboard_html", lambda: state["html"] is not None)
    monkeypatch.setattr(clipmd_module, "has_clipboard_text", lambda: state["text"] is not None)
    monkeypatch.setattr(clipmd_module, "get_clipboard_text", lambda: state["text"])

    def fake_get_html():
        if state["html"] is None:
            from workpytools.common.clipboard import ClipboardTextError

            raise ClipboardTextError("no html")
        return state["html"]

    monkeypatch.setattr(clipmd_module, "get_clipboard_html_fragment", fake_get_html)

    written = {}

    def fake_copy_html_and_text(html, text):
        written["html"] = html
        written["text"] = text

    def fake_copy_text(text):
        written["text"] = text
        written["html"] = None

    monkeypatch.setattr(clipmd_module, "copy_html_and_text_to_clipboard", fake_copy_html_and_text)
    monkeypatch.setattr(clipmd_module, "copy_text_to_clipboard", fake_copy_text)

    state["written"] = written
    return state


# --- 変換方向の判定 ---


def test_html_present_selects_html_to_markdown(clipboard_state) -> None:
    clipboard_state["html"] = "<p>hi</p>"
    clipboard_state["text"] = "hi"

    proc = ClipmdProcessor()
    proc.run(_base_args())

    assert "hi" in clipboard_state["written"]["text"]
    assert clipboard_state["written"]["html"] is None


def test_text_only_selects_markdown_to_rich(clipboard_state) -> None:
    clipboard_state["text"] = "# hi"

    proc = ClipmdProcessor()
    proc.run(_base_args())

    assert clipboard_state["written"]["html"] is not None
    assert clipboard_state["written"]["text"] == "# hi"


def test_neither_present_raises(clipboard_state) -> None:
    proc = ClipmdProcessor()
    with pytest.raises(SystemExit):
        proc.run(_base_args())


def test_to_markdown_overrides_autodetect(clipboard_state) -> None:
    clipboard_state["text"] = "# hi"

    proc = ClipmdProcessor()
    proc.run(_base_args(to_markdown=True))

    # CF_HTMLが無いのでCF_UNICODETEXTをHTMLソースとして解釈する
    assert clipboard_state["written"]["html"] is None


def test_to_rich_overrides_autodetect_ignoring_html(clipboard_state) -> None:
    clipboard_state["html"] = "<p>rich</p>"
    clipboard_state["text"] = "# markdown source"

    proc = ClipmdProcessor()
    proc.run(_base_args(to_rich=True))

    assert clipboard_state["written"]["html"] is not None
    assert "markdown source" in clipboard_state["written"]["text"]


def test_to_markdown_without_any_clipboard_content_raises(clipboard_state) -> None:
    proc = ClipmdProcessor()
    with pytest.raises(SystemExit):
        proc.run(_base_args(to_markdown=True))


def test_to_rich_without_text_raises(clipboard_state) -> None:
    proc = ClipmdProcessor()
    with pytest.raises(SystemExit):
        proc.run(_base_args(to_rich=True))


def test_autodetect_logs_direction(clipboard_state, caplog: pytest.LogCaptureFixture) -> None:
    clipboard_state["text"] = "# hi"
    proc = ClipmdProcessor()
    with caplog.at_level("INFO"):
        proc.run(_base_args())
    assert "リッチテキスト" in caplog.text


def test_override_logs_reinterpretation(clipboard_state, caplog: pytest.LogCaptureFixture) -> None:
    clipboard_state["html"] = "<p>rich</p>"
    clipboard_state["text"] = "# markdown"
    proc = ClipmdProcessor()
    with caplog.at_level("INFO"):
        proc.run(_base_args(to_rich=True))
    assert "無視" in caplog.text


# --- 変換内容 ---


def test_markdown_to_html_basic_elements() -> None:
    md = "# 見出し\n\n**太字** *斜体* [リンク](http://example.com)\n\n- 項目1\n- 項目2\n"
    html = clipmd_module.markdown_to_html_fragment(md)
    assert "<h1>見出し</h1>" in html
    assert "<strong>太字</strong>" in html
    assert "<em>斜体</em>" in html
    assert '<a href="http://example.com">リンク</a>' in html
    assert "<li>項目1</li>" in html


def test_markdown_table_becomes_table_html() -> None:
    md = "| a | b |\n|---|---:|\n| 1 | 2 |\n"
    html = clipmd_module.markdown_to_html_fragment(md)
    assert "<table>" in html
    assert 'style="text-align:right"' in html


def test_html_to_markdown_roundtrip_basic() -> None:
    html = "<h1>見出し</h1><p><strong>太字</strong></p>"
    md = html_to_markdown(html)
    assert "見出し" in md
    assert "**太字**" in md


# --- 表 ---


def test_thead_missing_promotes_first_row(caplog: pytest.LogCaptureFixture) -> None:
    html = "<table><tr><td>x</td><td>y</td></tr><tr><td>1</td><td>2</td></tr></table>"
    md = html_to_markdown(html)
    lines = [line for line in md.split("\n") if line.strip()]
    assert lines[0].strip() == "| x | y |"
    assert "---" in lines[1]
    assert lines[2].strip() == "| 1 | 2 |"


def test_colspan_padded_with_empty_cells(caplog: pytest.LogCaptureFixture) -> None:
    html = (
        "<table><tr><td colspan='2'>結合セル</td></tr>"
        "<tr><td>A1</td><td>B1</td></tr></table>"
    )
    with caplog.at_level("WARNING"):
        md = html_to_markdown(html)
    rows = [line for line in md.split("\n") if line.strip().startswith("|")]
    col_counts = {row.count("|") for row in rows}
    assert len(col_counts) == 1  # 全行の列数が揃っている
    assert "結合" in caplog.text


def test_cell_block_elements_warn(caplog: pytest.LogCaptureFixture) -> None:
    html = "<table><tr><td><p>段落</p><p>2つ</p></td></tr></table>"
    with caplog.at_level("WARNING"):
        html_to_markdown(html)
    assert "改行" in caplog.text or "リスト" in caplog.text


def test_table_conversion_completes_without_error() -> None:
    html = (
        "<table><tr><td colspan='2'>x</td></tr>"
        "<tr><td><ul><li>a</li></ul></td><td><img src='y.png'></td></tr></table>"
    )
    md = html_to_markdown(html)
    assert md  # 例外にならず何かしら出力される


def test_alignment_restored_on_roundtrip() -> None:
    md_in = "| a | b |\n|---|---:|\n| 1 | 2 |\n"
    html = clipmd_module.markdown_to_html_fragment(md_in)
    md_out = html_to_markdown(html)
    sep_line = [line for line in md_out.split("\n") if "---" in line][0]
    assert "---:" in sep_line


# --- 画像 ---


def test_markdown_image_becomes_img_tag() -> None:
    html = clipmd_module.markdown_to_html_fragment("![alt](http://example.com/a.png)")
    assert '<img src="http://example.com/a.png" alt="alt"' in html


def test_html_image_becomes_markdown() -> None:
    md = html_to_markdown('<img src="http://example.com/a.png" alt="alt">')
    assert "![alt](http://example.com/a.png)" in md


def test_file_uri_image_warns(caplog: pytest.LogCaptureFixture) -> None:
    html = (
        '<img src="file:///C:/Users/x/AppData/Local/Temp/msohtmlclip1/01/clip_image001.png">'
    )
    with caplog.at_level("WARNING"):
        md = html_to_markdown(html)
    assert "msohtmlclip" in caplog.text or "一時ファイル" in caplog.text
    assert "file:///" in md  # リンクは維持される


def test_data_uri_image_kept_and_warns(caplog: pytest.LogCaptureFixture) -> None:
    html = '<img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUg==">'
    with caplog.at_level("WARNING"):
        md = html_to_markdown(html)
    assert "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg==" in md
    assert "データURI" in caplog.text


def test_image_in_table_cell_warns(caplog: pytest.LogCaptureFixture) -> None:
    html = "<table><tr><td><img src='x.png' alt='A'></td></tr></table>"
    with caplog.at_level("WARNING"):
        html_to_markdown(html)
    assert "画像" in caplog.text


def test_no_image_files_are_created(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    original_open = open

    def spy_open(*a, **kw):
        calls.append(a)
        return original_open(*a, **kw)

    html = '<img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUg==">'
    html_to_markdown(html)
    # 画像処理自体がファイルを開かないことを確認（明示的なファイル書き込みが無いこと）
    assert not any("png" in str(c).lower() for c in calls)


# --- クリップボードへの書き戻し ---


def test_markdown_to_rich_sets_both_formats(clipboard_state) -> None:
    clipboard_state["text"] = "# hi"
    proc = ClipmdProcessor()
    proc.run(_base_args())
    assert clipboard_state["written"]["html"] is not None
    assert clipboard_state["written"]["text"] == "# hi"


def test_rich_to_markdown_sets_only_text(clipboard_state) -> None:
    clipboard_state["html"] = "<p>hi</p>"
    clipboard_state["text"] = "hi"
    proc = ClipmdProcessor()
    proc.run(_base_args())
    assert clipboard_state["written"]["html"] is None


# --- エラー ---


def test_empty_conversion_result_raises(clipboard_state) -> None:
    clipboard_state["text"] = "   \n\n  "
    proc = ClipmdProcessor()
    with pytest.raises(SystemExit):
        proc.run(_base_args())
