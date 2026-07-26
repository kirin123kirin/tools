import argparse
from pathlib import Path

import pytest

from tools.common import browser_preview as browser_preview_module
from tools.processing import clipview as clipview_module
from tools.processing.clipview import ClipviewProcessor, wrap_preview_html


def _base_args(**overrides: object) -> argparse.Namespace:
    defaults = dict(markdown=False, html=False, svg=False, no_open=True)
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


@pytest.fixture
def clipboard_state(monkeypatch: pytest.MonkeyPatch) -> dict:
    state = {"html": None, "text": None}
    monkeypatch.setattr(clipview_module, "has_clipboard_html", lambda: state["html"] is not None)
    monkeypatch.setattr(clipview_module, "has_clipboard_text", lambda: state["text"] is not None)
    monkeypatch.setattr(clipview_module, "get_clipboard_text", lambda: state["text"])

    def fake_get_html():
        if state["html"] is None:
            from tools.common.clipboard import ClipboardTextError

            raise ClipboardTextError("no html")
        return state["html"]

    monkeypatch.setattr(clipview_module, "get_clipboard_html_fragment", fake_get_html)
    return state


@pytest.fixture
def temp_preview_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setattr(browser_preview_module.tempfile, "gettempdir", lambda: str(tmp_path))
    return tmp_path


@pytest.fixture
def no_browser(monkeypatch: pytest.MonkeyPatch) -> list:
    calls: list[str] = []
    monkeypatch.setattr(browser_preview_module.webbrowser, "open", lambda url: calls.append(url))
    return calls


# --- 入力判別 ---


def test_html_present_used_for_preview(clipboard_state, temp_preview_dir, no_browser) -> None:
    clipboard_state["html"] = "<p>rich html</p>"
    clipboard_state["text"] = "rich html"

    proc = ClipviewProcessor()
    proc.run(_base_args())

    written = (temp_preview_dir / clipview_module._PREVIEW_FILENAME).read_text(encoding="utf-8")
    assert "rich html" in written


def test_text_only_converted_as_markdown(clipboard_state, temp_preview_dir, no_browser) -> None:
    clipboard_state["text"] = "# Heading"

    proc = ClipviewProcessor()
    proc.run(_base_args())

    written = (temp_preview_dir / clipview_module._PREVIEW_FILENAME).read_text(encoding="utf-8")
    assert "<h1>Heading</h1>" in written


def test_neither_present_raises(clipboard_state, temp_preview_dir, no_browser) -> None:
    proc = ClipviewProcessor()
    with pytest.raises(SystemExit):
        proc.run(_base_args())


def test_markdown_flag_overrides_autodetect(clipboard_state, temp_preview_dir, no_browser) -> None:
    clipboard_state["html"] = "<p>ignored</p>"
    clipboard_state["text"] = "# from markdown"

    proc = ClipviewProcessor()
    proc.run(_base_args(markdown=True))

    written = (temp_preview_dir / clipview_module._PREVIEW_FILENAME).read_text(encoding="utf-8")
    assert "<h1>from markdown</h1>" in written


def test_html_flag_overrides_autodetect(clipboard_state, temp_preview_dir, no_browser) -> None:
    clipboard_state["html"] = "<p>explicit html</p>"
    clipboard_state["text"] = "# should not be used"

    proc = ClipviewProcessor()
    proc.run(_base_args(html=True))

    written = (temp_preview_dir / clipview_module._PREVIEW_FILENAME).read_text(encoding="utf-8")
    assert "explicit html" in written


# --- SVG ---


def test_svg_autodetected_and_written_as_is(
    clipboard_state, temp_preview_dir, no_browser
) -> None:
    svg = '<svg xmlns="http://www.w3.org/2000/svg"><circle r="5"/></svg>'
    clipboard_state["text"] = svg

    ClipviewProcessor().run(_base_args())

    written = (temp_preview_dir / clipview_module._SVG_PREVIEW_FILENAME).read_text(
        encoding="utf-8"
    )
    assert written == svg
    # HTMLラップされていないこと（<html>/<body>タグが追加されていない）
    assert "<html>" not in written


def test_svg_leading_whitespace_still_detected(
    clipboard_state, temp_preview_dir, no_browser
) -> None:
    clipboard_state["text"] = "  \n<svg><rect/></svg>"

    ClipviewProcessor().run(_base_args())

    assert (temp_preview_dir / clipview_module._SVG_PREVIEW_FILENAME).exists()
    assert not (temp_preview_dir / clipview_module._PREVIEW_FILENAME).exists()


def test_non_svg_text_not_treated_as_svg(
    clipboard_state, temp_preview_dir, no_browser
) -> None:
    clipboard_state["text"] = "# Markdown heading"

    ClipviewProcessor().run(_base_args())

    assert not (temp_preview_dir / clipview_module._SVG_PREVIEW_FILENAME).exists()
    assert (temp_preview_dir / clipview_module._PREVIEW_FILENAME).exists()


def test_svg_flag_forces_svg_handling(clipboard_state, temp_preview_dir, no_browser) -> None:
    clipboard_state["text"] = "<svg><rect/></svg>"

    ClipviewProcessor().run(_base_args(svg=True))

    assert (temp_preview_dir / clipview_module._SVG_PREVIEW_FILENAME).exists()


def test_svg_flag_without_clipboard_text_raises(
    clipboard_state, temp_preview_dir, no_browser
) -> None:
    with pytest.raises(SystemExit):
        ClipviewProcessor().run(_base_args(svg=True))


def test_markdown_flag_bypasses_svg_autodetect(
    clipboard_state, temp_preview_dir, no_browser
) -> None:
    # --markdown指定時は<svgで始まっていてもMarkdownとして扱われる
    clipboard_state["text"] = "<svg>looks like svg but forced markdown</svg>"

    ClipviewProcessor().run(_base_args(markdown=True))

    assert not (temp_preview_dir / clipview_module._SVG_PREVIEW_FILENAME).exists()
    assert (temp_preview_dir / clipview_module._PREVIEW_FILENAME).exists()


def test_svg_empty_result_raises(clipboard_state, temp_preview_dir, no_browser) -> None:
    clipboard_state["text"] = "   "
    with pytest.raises(SystemExit):
        ClipviewProcessor().run(_base_args(svg=True))


def test_svg_second_run_overwrites_same_file(
    clipboard_state, temp_preview_dir, no_browser
) -> None:
    clipboard_state["text"] = "<svg>first</svg>"
    ClipviewProcessor().run(_base_args())
    clipboard_state["text"] = "<svg>second</svg>"
    ClipviewProcessor().run(_base_args())

    files = list(temp_preview_dir.glob("*.svg"))
    assert len(files) == 1
    assert "second" in files[0].read_text(encoding="utf-8")


def test_svg_browser_url_has_cache_busting_query(
    clipboard_state, temp_preview_dir, monkeypatch
) -> None:
    clipboard_state["text"] = "<svg><rect/></svg>"
    calls = []
    monkeypatch.setattr(browser_preview_module.webbrowser, "open", lambda url: calls.append(url))

    ClipviewProcessor().run(_base_args(no_open=False))

    assert "?v=" in calls[0]
    assert calls[0].endswith(".svg?v=" + calls[0].split("?v=")[1])


# --- 出力 ---


def test_writes_to_fixed_path_in_temp(clipboard_state, temp_preview_dir, no_browser) -> None:
    clipboard_state["text"] = "hi"
    proc = ClipviewProcessor()
    proc.run(_base_args())
    assert (temp_preview_dir / clipview_module._PREVIEW_FILENAME).exists()


def test_second_run_overwrites_same_file(clipboard_state, temp_preview_dir, no_browser) -> None:
    clipboard_state["text"] = "first"
    ClipviewProcessor().run(_base_args())
    clipboard_state["text"] = "second"
    ClipviewProcessor().run(_base_args())

    files = list(temp_preview_dir.glob("*.html"))
    assert len(files) == 1
    assert "second" in files[0].read_text(encoding="utf-8")


def test_path_logged(clipboard_state, temp_preview_dir, no_browser, caplog) -> None:
    clipboard_state["text"] = "hi"
    with caplog.at_level("INFO"):
        ClipviewProcessor().run(_base_args())
    assert str(temp_preview_dir) in caplog.text


def test_html_wraps_with_charset_and_cache_control() -> None:
    html = wrap_preview_html("<p>x</p>")
    assert '<meta charset="utf-8">' in html
    assert "Cache-Control" in html
    assert "no-store" in html


def test_html_has_dark_mode_media_query() -> None:
    html = wrap_preview_html("<p>x</p>")
    assert "prefers-color-scheme: dark" in html


def test_cf_html_fragment_wrapped_into_full_document(
    clipboard_state, temp_preview_dir, no_browser
) -> None:
    clipboard_state["html"] = "<p>fragment only</p>"
    clipboard_state["text"] = "fragment only"
    ClipviewProcessor().run(_base_args())
    written = (temp_preview_dir / clipview_module._PREVIEW_FILENAME).read_text(encoding="utf-8")
    assert "<html>" in written
    assert "<body>" in written
    assert written.strip() != "<p>fragment only</p>"


def test_markdown_fragment_wrapped_into_full_document(
    clipboard_state, temp_preview_dir, no_browser
) -> None:
    clipboard_state["text"] = "plain markdown"
    ClipviewProcessor().run(_base_args())
    written = (temp_preview_dir / clipview_module._PREVIEW_FILENAME).read_text(encoding="utf-8")
    assert "<html>" in written
    assert "<body>" in written


def test_no_external_cdn_references_in_style() -> None:
    html = wrap_preview_html("<p>x</p>")
    style_section = html.split("<style>")[1].split("</style>")[0]
    assert "http://" not in style_section
    assert "https://" not in style_section


# --- ブラウザ起動 ---


def test_browser_opened_by_default(clipboard_state, temp_preview_dir, monkeypatch) -> None:
    clipboard_state["text"] = "hi"
    calls = []
    monkeypatch.setattr(browser_preview_module.webbrowser, "open", lambda url: calls.append(url))

    proc = ClipviewProcessor()
    proc.run(_base_args(no_open=False))

    assert len(calls) == 1


def test_no_open_skips_browser(clipboard_state, temp_preview_dir, no_browser) -> None:
    clipboard_state["text"] = "hi"
    proc = ClipviewProcessor()
    proc.run(_base_args(no_open=True))
    assert no_browser == []


def test_no_open_still_prints_path(clipboard_state, temp_preview_dir, no_browser, capsys) -> None:
    clipboard_state["text"] = "hi"
    ClipviewProcessor().run(_base_args(no_open=True))
    captured = capsys.readouterr()
    assert clipview_module._PREVIEW_FILENAME in captured.out


def test_browser_url_has_cache_busting_query(
    clipboard_state, temp_preview_dir, monkeypatch
) -> None:
    clipboard_state["text"] = "hi"
    calls = []
    monkeypatch.setattr(browser_preview_module.webbrowser, "open", lambda url: calls.append(url))

    ClipviewProcessor().run(_base_args(no_open=False))

    assert "?v=" in calls[0]


def test_two_runs_have_different_query_values(
    clipboard_state, temp_preview_dir, monkeypatch
) -> None:
    clipboard_state["text"] = "hi"
    calls = []
    monkeypatch.setattr(browser_preview_module.webbrowser, "open", lambda url: calls.append(url))

    ClipviewProcessor().run(_base_args(no_open=False))
    ClipviewProcessor().run(_base_args(no_open=False))

    query1 = calls[0].split("?v=")[1]
    query2 = calls[1].split("?v=")[1]
    assert query1 != query2


# --- エラー ---


def test_empty_result_raises(clipboard_state, temp_preview_dir, no_browser) -> None:
    clipboard_state["text"] = "   \n  "
    proc = ClipviewProcessor()
    with pytest.raises(SystemExit):
        proc.run(_base_args())
