import argparse
from unittest.mock import MagicMock

import pytest

from workpytools.common.powerpoint import NoActivePresentationError, PowerPointNotRunningError
from workpytools.processing import umekomi as umekomi_module
from workpytools.processing.umekomi import UmekomiProcessor

_SELECTION_NONE = 0
_SELECTION_SHAPES = 2
_MSO_TEXT_BOX = 17
_MSO_RECTANGLE = 1


def _base_args(**overrides: object) -> argparse.Namespace:
    defaults: dict[str, object] = dict(dry_run=False)
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _make_shape(
    left: float,
    top: float,
    width: float,
    height: float,
    shape_type: int = _MSO_RECTANGLE,
    text: str = "",
    font_name: str = "Meiryo",
    font_size: float = 14.0,
    bold: int = 0,
    color: int = 0,
    alignment: int = 1,
    has_text_frame: bool = True,
) -> MagicMock:
    shape = MagicMock()
    shape.Type = shape_type
    shape.HasTextFrame = has_text_frame
    shape.Left = left
    shape.Top = top
    shape.Width = width
    shape.Height = height

    text_range = shape.TextFrame.TextRange
    text_range.Text = text
    text_range.Font.Name = font_name
    text_range.Font.Size = font_size
    text_range.Font.Bold = bold
    text_range.Font.Color.RGB = color
    text_range.ParagraphFormat.Alignment = alignment
    return shape


def _make_app_with_selection(selected: list, selection_type: int = _SELECTION_SHAPES) -> MagicMock:
    app = MagicMock()
    app.ActiveWindow.Selection.Type = selection_type
    shape_range = app.ActiveWindow.Selection.ShapeRange
    shape_range.Count = len(selected)
    shape_range.Item.side_effect = lambda i: selected[i - 1]
    return app


def _setup_running(monkeypatch: pytest.MonkeyPatch, app: MagicMock) -> None:
    monkeypatch.setattr(umekomi_module, "get_running_powerpoint", lambda: app)
    monkeypatch.setattr(umekomi_module, "get_active_presentation", lambda a: MagicMock())


# --- 重なり判定・組み合わせ ---


def test_text_box_center_inside_host_is_embedded(monkeypatch: pytest.MonkeyPatch) -> None:
    host = _make_shape(left=0, top=0, width=200, height=100, shape_type=_MSO_RECTANGLE, text="")
    tb = _make_shape(left=50, top=30, width=100, height=20, shape_type=_MSO_TEXT_BOX, text="hello")
    app = _make_app_with_selection([host, tb])
    _setup_running(monkeypatch, app)

    result = UmekomiProcessor().run(_base_args())

    assert result == 0
    assert host.TextFrame.TextRange.Text == "hello"
    tb.Delete.assert_called_once()


def test_text_box_center_outside_host_not_embedded(monkeypatch: pytest.MonkeyPatch) -> None:
    host = _make_shape(left=0, top=0, width=50, height=50, shape_type=_MSO_RECTANGLE, text="")
    tb = _make_shape(
        left=500, top=500, width=100, height=20, shape_type=_MSO_TEXT_BOX, text="far away"
    )
    app = _make_app_with_selection([host, tb])
    _setup_running(monkeypatch, app)

    result = UmekomiProcessor().run(_base_args())

    assert result == 0
    tb.Delete.assert_not_called()


def test_multiple_text_boxes_merged_in_top_order(monkeypatch: pytest.MonkeyPatch) -> None:
    host = _make_shape(left=0, top=0, width=200, height=200, shape_type=_MSO_RECTANGLE, text="")
    tb_bottom = _make_shape(
        left=10, top=100, width=100, height=20, shape_type=_MSO_TEXT_BOX, text="second"
    )
    tb_top = _make_shape(
        left=10, top=20, width=100, height=20, shape_type=_MSO_TEXT_BOX, text="first"
    )
    app = _make_app_with_selection([host, tb_bottom, tb_top])  # 選択順はバラバラ
    _setup_running(monkeypatch, app)

    UmekomiProcessor().run(_base_args())

    assert host.TextFrame.TextRange.Text == "first\rsecond"


# --- 既存テキストとの結合 ---


def test_existing_host_text_prepended_when_text_box_below_center(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _make_shape(
        left=0, top=0, width=200, height=100, shape_type=_MSO_RECTANGLE, text="host label"
    )
    tb = _make_shape(
        left=10, top=80, width=100, height=20, shape_type=_MSO_TEXT_BOX, text="overlay"
    )
    app = _make_app_with_selection([host, tb])
    _setup_running(monkeypatch, app)

    UmekomiProcessor().run(_base_args())

    assert host.TextFrame.TextRange.Text == "host label\roverlay"


def test_existing_host_text_appended_when_text_box_above_center(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _make_shape(
        left=0, top=0, width=200, height=100, shape_type=_MSO_RECTANGLE, text="host label"
    )
    tb = _make_shape(
        left=10, top=10, width=100, height=20, shape_type=_MSO_TEXT_BOX, text="overlay"
    )
    app = _make_app_with_selection([host, tb])
    _setup_running(monkeypatch, app)

    UmekomiProcessor().run(_base_args())

    assert host.TextFrame.TextRange.Text == "overlay\rhost label"


# --- 書式の引き継ぎ ---


def test_style_from_topmost_text_box_applied(monkeypatch: pytest.MonkeyPatch) -> None:
    host = _make_shape(left=0, top=0, width=200, height=200, shape_type=_MSO_RECTANGLE, text="")
    tb_top = _make_shape(
        left=10, top=20, width=100, height=20, shape_type=_MSO_TEXT_BOX,
        text="first", font_name="Arial", font_size=20.0, bold=-1, color=255,
    )
    tb_bottom = _make_shape(
        left=10, top=100, width=100, height=20, shape_type=_MSO_TEXT_BOX,
        text="second", font_name="Meiryo", font_size=10.0, bold=0, color=0,
    )
    app = _make_app_with_selection([host, tb_top, tb_bottom])
    _setup_running(monkeypatch, app)

    UmekomiProcessor().run(_base_args())

    assert host.TextFrame.TextRange.Font.Name == "Arial"
    assert host.TextFrame.TextRange.Font.Size == 20.0
    assert host.TextFrame.TextRange.Font.Bold == -1
    assert host.TextFrame.TextRange.Font.Color.RGB == 255


# --- Undo ---


def test_start_new_undo_entry_called(monkeypatch: pytest.MonkeyPatch) -> None:
    host = _make_shape(left=0, top=0, width=200, height=100, shape_type=_MSO_RECTANGLE, text="")
    tb = _make_shape(left=10, top=10, width=100, height=20, shape_type=_MSO_TEXT_BOX, text="hello")
    app = _make_app_with_selection([host, tb])
    _setup_running(monkeypatch, app)

    UmekomiProcessor().run(_base_args())

    app.StartNewUndoEntry.assert_called_once()


# --- --dry-run ---


def test_dry_run_does_not_modify_or_delete(monkeypatch: pytest.MonkeyPatch) -> None:
    host = _make_shape(left=0, top=0, width=200, height=100, shape_type=_MSO_RECTANGLE, text="")
    tb = _make_shape(left=10, top=10, width=100, height=20, shape_type=_MSO_TEXT_BOX, text="hello")
    app = _make_app_with_selection([host, tb])
    _setup_running(monkeypatch, app)

    UmekomiProcessor().run(_base_args(dry_run=True))

    tb.Delete.assert_not_called()
    assert host.TextFrame.TextRange.Text == ""
    app.StartNewUndoEntry.assert_not_called()


def test_dry_run_prints_pairs(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    host = _make_shape(left=0, top=0, width=200, height=100, shape_type=_MSO_RECTANGLE, text="")
    tb = _make_shape(left=10, top=10, width=100, height=20, shape_type=_MSO_TEXT_BOX, text="hello")
    app = _make_app_with_selection([host, tb])
    _setup_running(monkeypatch, app)

    UmekomiProcessor().run(_base_args(dry_run=True))

    out = capsys.readouterr().out
    assert "hello" in out


# --- 対象なし ---


def test_no_overlap_returns_success_with_hint(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    host = _make_shape(left=0, top=0, width=50, height=50, shape_type=_MSO_RECTANGLE, text="")
    tb = _make_shape(left=500, top=500, width=100, height=20, shape_type=_MSO_TEXT_BOX, text="far")
    app = _make_app_with_selection([host, tb])
    _setup_running(monkeypatch, app)

    result = UmekomiProcessor().run(_base_args())

    assert result == 0
    out = capsys.readouterr().out
    assert "見つかりませんでした" in out


def test_blank_text_box_excluded(monkeypatch: pytest.MonkeyPatch) -> None:
    host = _make_shape(left=0, top=0, width=200, height=100, shape_type=_MSO_RECTANGLE, text="")
    tb = _make_shape(left=10, top=10, width=100, height=20, shape_type=_MSO_TEXT_BOX, text="   ")
    app = _make_app_with_selection([host, tb])
    _setup_running(monkeypatch, app)

    result = UmekomiProcessor().run(_base_args())

    assert result == 0
    tb.Delete.assert_not_called()


# --- 選択・エラー処理 ---


def test_single_shape_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    host = _make_shape(left=0, top=0, width=200, height=100, shape_type=_MSO_RECTANGLE)
    app = _make_app_with_selection([host])
    _setup_running(monkeypatch, app)

    with pytest.raises(SystemExit):
        UmekomiProcessor().run(_base_args())


def test_no_selection_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _make_app_with_selection([], selection_type=_SELECTION_NONE)
    _setup_running(monkeypatch, app)

    with pytest.raises(SystemExit):
        UmekomiProcessor().run(_base_args())


def test_powerpoint_not_running_raises_without_new_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_not_running():
        raise PowerPointNotRunningError("not running")

    monkeypatch.setattr(umekomi_module, "get_running_powerpoint", raise_not_running)
    dispatch = MagicMock()
    monkeypatch.setattr("win32com.client.Dispatch", dispatch, raising=False)

    with pytest.raises(SystemExit):
        UmekomiProcessor().run(_base_args())

    dispatch.assert_not_called()


def test_no_active_presentation_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(umekomi_module, "get_running_powerpoint", lambda: MagicMock())

    def raise_no_active(app):
        raise NoActivePresentationError("no active")

    monkeypatch.setattr(umekomi_module, "get_active_presentation", raise_no_active)

    with pytest.raises(SystemExit):
        UmekomiProcessor().run(_base_args())


def test_com_exception_mentions_undo(monkeypatch: pytest.MonkeyPatch) -> None:
    host = _make_shape(left=0, top=0, width=200, height=100, shape_type=_MSO_RECTANGLE, text="")
    tb = _make_shape(left=10, top=10, width=100, height=20, shape_type=_MSO_TEXT_BOX, text="hello")
    tb.Delete.side_effect = RuntimeError("boom")
    app = _make_app_with_selection([host, tb])
    _setup_running(monkeypatch, app)

    with pytest.raises(SystemExit, match="Ctrl\\+Z"):
        UmekomiProcessor().run(_base_args())
