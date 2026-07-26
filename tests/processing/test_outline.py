import argparse
from unittest.mock import MagicMock

import pytest

from tools.common.clipboard import ClipboardTextError
from tools.common.powerpoint import NoActivePresentationError, PowerPointNotRunningError
from tools.processing import outline as outline_module
from tools.processing.outline import OutlineProcessor


def _base_args(**overrides: object) -> argparse.Namespace:
    return argparse.Namespace(**overrides)


@pytest.fixture
def clipboard_state(monkeypatch: pytest.MonkeyPatch) -> dict:
    state = {"text": None}

    def fake_get() -> str:
        if state["text"] is None:
            raise ClipboardTextError("クリップボードにテキストがありません")
        return state["text"]

    monkeypatch.setattr(outline_module, "get_clipboard_text", fake_get)
    return state


def _make_presentation(existing_slide_count: int = 0) -> MagicMock:
    presentation = MagicMock()
    presentation.Slides.Count = existing_slide_count

    added_slides = []

    def fake_add(index, layout):
        slide = MagicMock()
        slide._index = index
        # MagicMockはPlaceholders(1)/Placeholders(2)のような引数違いの呼び出しを
        # 区別せず同じ子Mockを返すため、明示的に別オブジェクトを割り当てる。
        placeholder_1 = MagicMock()
        placeholder_2 = MagicMock()
        slide.Shapes.Placeholders.side_effect = lambda i: placeholder_1 if i == 1 else placeholder_2
        added_slides.append(slide)
        presentation.Slides.Count = index
        return slide

    presentation.Slides.Add.side_effect = fake_add
    presentation._added_slides = added_slides
    return presentation


def test_clipboard_empty_raises(clipboard_state) -> None:
    clipboard_state["text"] = None
    with pytest.raises(SystemExit):
        OutlineProcessor().run(_base_args())


def test_no_extractable_items_raises_without_touching_powerpoint(
    clipboard_state, monkeypatch: pytest.MonkeyPatch
) -> None:
    clipboard_state["text"] = "   \n\n  "
    get_running = MagicMock()
    monkeypatch.setattr(outline_module, "get_running_powerpoint", get_running)

    with pytest.raises(SystemExit):
        OutlineProcessor().run(_base_args())

    get_running.assert_not_called()


def test_active_object_success_uses_active_window_presentation(
    clipboard_state, monkeypatch: pytest.MonkeyPatch
) -> None:
    clipboard_state["text"] = "タイトル\tリード文"
    presentation = _make_presentation(existing_slide_count=0)
    app = MagicMock()

    monkeypatch.setattr(outline_module, "get_running_powerpoint", lambda: app)
    monkeypatch.setattr(outline_module, "get_active_presentation", lambda a: presentation)

    OutlineProcessor().run(_base_args())

    assert presentation.Slides.Add.call_count == 1


def test_powerpoint_not_running_launches_new_instance(
    clipboard_state, monkeypatch: pytest.MonkeyPatch
) -> None:
    clipboard_state["text"] = "タイトル\tリード文"

    def raise_not_running():
        raise PowerPointNotRunningError("not running")

    monkeypatch.setattr(outline_module, "get_running_powerpoint", raise_not_running)

    fake_win32com = MagicMock()
    new_app = MagicMock()
    fake_win32com.client.Dispatch.return_value = new_app
    presentation = _make_presentation()
    new_app.Presentations.Add.return_value = presentation

    monkeypatch.setitem(__import__("sys").modules, "win32com.client", fake_win32com.client)
    monkeypatch.setitem(__import__("sys").modules, "win32com", fake_win32com)

    OutlineProcessor().run(_base_args())

    fake_win32com.client.Dispatch.assert_called_once_with("PowerPoint.Application")
    assert new_app.Visible is True
    new_app.Presentations.Add.assert_called_once()


def test_no_active_presentation_creates_new_one(
    clipboard_state, monkeypatch: pytest.MonkeyPatch
) -> None:
    clipboard_state["text"] = "タイトル\tリード文"
    app = MagicMock()
    presentation = _make_presentation()
    app.Presentations.Add.return_value = presentation

    monkeypatch.setattr(outline_module, "get_running_powerpoint", lambda: app)

    def raise_no_active(a):
        raise NoActivePresentationError("no active")

    monkeypatch.setattr(outline_module, "get_active_presentation", raise_no_active)

    OutlineProcessor().run(_base_args())

    app.Presentations.Add.assert_called_once()


def test_slide_count_matches_extracted_items(
    clipboard_state, monkeypatch: pytest.MonkeyPatch
) -> None:
    clipboard_state["text"] = "A\tbodyA\nB\tbodyB\nC\tbodyC"
    presentation = _make_presentation(existing_slide_count=0)
    monkeypatch.setattr(outline_module, "get_running_powerpoint", lambda: MagicMock())
    monkeypatch.setattr(outline_module, "get_active_presentation", lambda a: presentation)

    OutlineProcessor().run(_base_args())

    assert presentation.Slides.Add.call_count == 3


def test_placeholders_receive_title_and_body(
    clipboard_state, monkeypatch: pytest.MonkeyPatch
) -> None:
    clipboard_state["text"] = "タイトル\tリード文"
    presentation = _make_presentation()
    monkeypatch.setattr(outline_module, "get_running_powerpoint", lambda: MagicMock())
    monkeypatch.setattr(outline_module, "get_active_presentation", lambda a: presentation)

    OutlineProcessor().run(_base_args())

    slide = presentation._added_slides[0]
    assert slide.Shapes.Placeholders(1).TextFrame.TextRange.Text == "タイトル"
    assert slide.Shapes.Placeholders(2).TextFrame.TextRange.Text == "リード文"


def test_empty_body_sets_empty_string(clipboard_state, monkeypatch: pytest.MonkeyPatch) -> None:
    clipboard_state["text"] = "タイトルのみ"
    presentation = _make_presentation()
    monkeypatch.setattr(outline_module, "get_running_powerpoint", lambda: MagicMock())
    monkeypatch.setattr(outline_module, "get_active_presentation", lambda a: presentation)

    OutlineProcessor().run(_base_args())

    slide = presentation._added_slides[0]
    assert slide.Shapes.Placeholders(2).TextFrame.TextRange.Text == ""


def test_slides_added_at_tail_index_with_existing_slides(
    clipboard_state, monkeypatch: pytest.MonkeyPatch
) -> None:
    clipboard_state["text"] = "A\tbodyA\nB\tbodyB"
    presentation = _make_presentation(existing_slide_count=2)
    monkeypatch.setattr(outline_module, "get_running_powerpoint", lambda: MagicMock())
    monkeypatch.setattr(outline_module, "get_active_presentation", lambda a: presentation)

    OutlineProcessor().run(_base_args())

    calls = presentation.Slides.Add.call_args_list
    assert calls[0].args[0] == 3
    assert calls[1].args[0] == 4


def test_multiline_body_converted_to_cr(clipboard_state, monkeypatch: pytest.MonkeyPatch) -> None:
    clipboard_state["text"] = "タイトル\n行1\n行2"
    presentation = _make_presentation()
    monkeypatch.setattr(outline_module, "get_running_powerpoint", lambda: MagicMock())
    monkeypatch.setattr(outline_module, "get_active_presentation", lambda a: presentation)

    OutlineProcessor().run(_base_args())

    slide = presentation._added_slides[0]
    assert slide.Shapes.Placeholders(2).TextFrame.TextRange.Text == "行1\r行2"


def test_com_exception_raises_system_exit(
    clipboard_state, monkeypatch: pytest.MonkeyPatch
) -> None:
    clipboard_state["text"] = "タイトル\tリード文"
    presentation = MagicMock()
    presentation.Slides.Count = 0
    presentation.Slides.Add.side_effect = RuntimeError("boom")

    monkeypatch.setattr(outline_module, "get_running_powerpoint", lambda: MagicMock())
    monkeypatch.setattr(outline_module, "get_active_presentation", lambda a: presentation)

    with pytest.raises(SystemExit):
        OutlineProcessor().run(_base_args())
