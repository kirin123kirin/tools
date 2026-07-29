import argparse
from unittest.mock import MagicMock

import pytest

from workpytools.common.powerpoint import NoActivePresentationError, PowerPointNotRunningError
from workpytools.processing import mokuji as mokuji_module
from workpytools.processing.mokuji import MokujiProcessor


def _base_args(**overrides: object) -> argparse.Namespace:
    return argparse.Namespace(**overrides)


@pytest.fixture
def clipboard_state(monkeypatch: pytest.MonkeyPatch) -> dict:
    state = {"written": None}

    def fake_copy(text: str) -> None:
        state["written"] = text

    monkeypatch.setattr(mokuji_module, "copy_text_to_clipboard", fake_copy)
    return state


def _make_shape(text: str, top: float = 0.0, has_text_frame: bool = True) -> MagicMock:
    shape = MagicMock()
    shape.HasTextFrame = has_text_frame
    shape.Top = top
    shape.TextFrame.TextRange.Text = text
    return shape


def _make_slide(
    title_text: str | None, has_title: bool, extra_shapes: list | None = None
) -> MagicMock:
    # slide.Shapesは実際のPowerPoint COM（レイトバインディング）に合わせて
    # Count + Item(i) でアクセスする。for...inの直接イテレーションは
    # 実機で動作しないため、モックもそれを再現しないようにする。
    slide = MagicMock()
    slide.Shapes.HasTitle = has_title
    if has_title:
        slide.Shapes.Title.TextFrame.TextRange.Text = title_text or ""
    shapes = list(extra_shapes or [])
    slide.Shapes.Count = len(shapes)
    slide.Shapes.Item.side_effect = lambda i: shapes[i - 1]
    return slide


def _make_presentation(slides: list) -> MagicMock:
    presentation = MagicMock()
    presentation.Slides.Count = len(slides)
    presentation.Slides.Item.side_effect = lambda i: slides[i - 1]
    return presentation


def _setup(monkeypatch: pytest.MonkeyPatch, presentation) -> None:
    monkeypatch.setattr(mokuji_module, "get_running_powerpoint", lambda: MagicMock())
    monkeypatch.setattr(mokuji_module, "get_active_presentation", lambda a: presentation)


# --- タイトル抽出の優先順位 ---


def test_title_placeholder_used_when_present(
    clipboard_state, monkeypatch: pytest.MonkeyPatch
) -> None:
    slide = _make_slide("正規タイトル", has_title=True)
    presentation = _make_presentation([slide])
    _setup(monkeypatch, presentation)

    MokujiProcessor().run(_base_args())

    assert clipboard_state["written"].strip() == "正規タイトル"


def test_empty_title_placeholder_falls_back_to_topmost_shape(
    clipboard_state, monkeypatch: pytest.MonkeyPatch
) -> None:
    top_shape = _make_shape("代用タイトル", top=10.0)
    other_shape = _make_shape("本文", top=100.0)
    slide = _make_slide("", has_title=True, extra_shapes=[other_shape, top_shape])
    presentation = _make_presentation([slide])
    _setup(monkeypatch, presentation)

    MokujiProcessor().run(_base_args())

    assert clipboard_state["written"].strip() == "代用タイトル"


def test_has_title_false_never_accesses_title(
    clipboard_state, monkeypatch: pytest.MonkeyPatch
) -> None:
    top_shape = _make_shape("白紙レイアウトの代用タイトル", top=10.0)
    slide = _make_slide(None, has_title=False, extra_shapes=[top_shape])

    # Titleにアクセスすると例外を出すようにして、アクセスされていないことを保証する
    def _raise_if_accessed(self: object) -> None:
        raise RuntimeError("should not access Title")

    type(slide.Shapes).Title = property(_raise_if_accessed)
    presentation = _make_presentation([slide])
    _setup(monkeypatch, presentation)

    MokujiProcessor().run(_base_args())

    assert clipboard_state["written"].strip() == "白紙レイアウトの代用タイトル"


def test_topmost_shape_selected_regardless_of_order(
    clipboard_state, monkeypatch: pytest.MonkeyPatch
) -> None:
    s1 = _make_shape("中間", top=50.0)
    s2 = _make_shape("一番上", top=5.0)
    s3 = _make_shape("下", top=200.0)
    slide = _make_slide("", has_title=True, extra_shapes=[s1, s2, s3])
    presentation = _make_presentation([slide])
    _setup(monkeypatch, presentation)

    MokujiProcessor().run(_base_args())

    assert clipboard_state["written"].strip() == "一番上"


def test_shape_without_text_frame_excluded_from_fallback(
    clipboard_state, monkeypatch: pytest.MonkeyPatch
) -> None:
    no_text = _make_shape("無視される", top=1.0, has_text_frame=False)
    real = _make_shape("代用タイトル", top=50.0)
    slide = _make_slide("", has_title=True, extra_shapes=[no_text, real])
    presentation = _make_presentation([slide])
    _setup(monkeypatch, presentation)

    MokujiProcessor().run(_base_args())

    assert clipboard_state["written"].strip() == "代用タイトル"


def test_blank_shape_excluded_from_fallback(
    clipboard_state, monkeypatch: pytest.MonkeyPatch
) -> None:
    blank = _make_shape("   ", top=1.0)
    real = _make_shape("代用タイトル", top=50.0)
    slide = _make_slide("", has_title=True, extra_shapes=[blank, real])
    presentation = _make_presentation([slide])
    _setup(monkeypatch, presentation)

    MokujiProcessor().run(_base_args())

    assert clipboard_state["written"].strip() == "代用タイトル"


def test_no_title_found_becomes_empty_string(
    clipboard_state, monkeypatch: pytest.MonkeyPatch
) -> None:
    slide = _make_slide(None, has_title=False, extra_shapes=[])
    presentation = _make_presentation([slide])
    _setup(monkeypatch, presentation)

    MokujiProcessor().run(_base_args())

    assert clipboard_state["written"].strip("\r\n") == ""


# --- 一覧の対応関係 ---


def test_list_length_matches_slide_count_with_blank_entries(
    clipboard_state, monkeypatch: pytest.MonkeyPatch
) -> None:
    s1 = _make_slide("タイトル1", has_title=True)
    s2 = _make_slide(None, has_title=False, extra_shapes=[])
    s3 = _make_slide("タイトル3", has_title=True)
    presentation = _make_presentation([s1, s2, s3])
    _setup(monkeypatch, presentation)

    MokujiProcessor().run(_base_args())

    lines = clipboard_state["written"].split("\r\n")
    assert lines == ["タイトル1", "", "タイトル3"]


def test_title_with_newline_flattened_to_space(
    clipboard_state, monkeypatch: pytest.MonkeyPatch
) -> None:
    slide = _make_slide("行1\r行2", has_title=True)
    presentation = _make_presentation([slide])
    _setup(monkeypatch, presentation)

    MokujiProcessor().run(_base_args())

    assert clipboard_state["written"].strip() == "行1 行2"


# --- 出力 ---


def test_output_is_crlf_joined(clipboard_state, monkeypatch: pytest.MonkeyPatch) -> None:
    s1 = _make_slide("A", has_title=True)
    s2 = _make_slide("B", has_title=True)
    presentation = _make_presentation([s1, s2])
    _setup(monkeypatch, presentation)

    MokujiProcessor().run(_base_args())

    assert clipboard_state["written"] == "A\r\nB"


def test_completion_message_includes_count_and_not_full_list(
    clipboard_state, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    s1 = _make_slide("A", has_title=True)
    s2 = _make_slide("B", has_title=True)
    presentation = _make_presentation([s1, s2])
    _setup(monkeypatch, presentation)

    MokujiProcessor().run(_base_args())

    out = capsys.readouterr().out
    assert "2件" in out
    assert "A" not in out
    assert "B" not in out


# --- エラー処理 ---


def test_powerpoint_not_running_raises_without_new_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_not_running():
        raise PowerPointNotRunningError("not running")

    monkeypatch.setattr(mokuji_module, "get_running_powerpoint", raise_not_running)
    dispatch = MagicMock()
    monkeypatch.setattr("win32com.client.Dispatch", dispatch, raising=False)

    with pytest.raises(SystemExit):
        MokujiProcessor().run(_base_args())

    dispatch.assert_not_called()


def test_no_active_presentation_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mokuji_module, "get_running_powerpoint", lambda: MagicMock())

    def raise_no_active(app):
        raise NoActivePresentationError("no active")

    monkeypatch.setattr(mokuji_module, "get_active_presentation", raise_no_active)

    with pytest.raises(SystemExit):
        MokujiProcessor().run(_base_args())


def test_zero_slides_returns_success_without_clipboard_write(
    clipboard_state, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    presentation = _make_presentation([])
    _setup(monkeypatch, presentation)

    result = MokujiProcessor().run(_base_args())

    assert result == 0
    assert clipboard_state["written"] is None
    assert "ありません" in capsys.readouterr().out


def test_com_exception_raises_system_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    presentation = MagicMock()
    presentation.Slides.Count = 1
    presentation.Slides.Item.side_effect = RuntimeError("boom")
    _setup(monkeypatch, presentation)

    with pytest.raises(SystemExit):
        MokujiProcessor().run(_base_args())
