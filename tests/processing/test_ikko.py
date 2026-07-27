import argparse
from unittest.mock import MagicMock

import pytest

from workpytools.common.powerpoint import NoActivePresentationError, PowerPointNotRunningError
from workpytools.processing import ikko as ikko_module
from workpytools.processing.ikko import IkkoProcessor

_SELECTION_NONE = 0
_SELECTION_SHAPES = 2


def _base_args(**overrides: object) -> argparse.Namespace:
    defaults = dict(
        dry_run=False,
        left_tolerance=1.0,
        line_step_min=0.8,
        line_step_max=2.2,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _make_com_shape(
    left: float = 100.0,
    top: float = 100.0,
    width: float = 200.0,
    height: float = 20.0,
    text: str = "line",
    font_name: str = "Meiryo",
    font_size: float = 14.0,
    bold: int = 0,
    color: int = 0,
    alignment: int = 1,
    paragraphs_count: int = 1,
    has_text_frame: bool = True,
) -> MagicMock:
    shape = MagicMock()
    shape.HasTextFrame = has_text_frame
    shape.Left = left
    shape.Top = top
    shape.Width = width
    shape.Height = height

    text_range = shape.TextFrame.TextRange
    text_range.Text = text
    text_range.Paragraphs.return_value.Count = paragraphs_count
    text_range.Font.Name = font_name
    text_range.Font.Size = font_size
    text_range.Font.Bold = bold
    text_range.Font.Color.RGB = color
    text_range.ParagraphFormat.Alignment = alignment
    return shape


def _make_app_with_shapes(shapes: list, selection_type: int = _SELECTION_NONE) -> MagicMock:
    app = MagicMock()
    app.ActiveWindow.Selection.Type = selection_type
    slide = app.ActiveWindow.View.Slide
    slide.Shapes.Count = len(shapes)
    slide.Shapes.Item.side_effect = lambda i: shapes[i - 1]
    return app


def _setup_running(monkeypatch: pytest.MonkeyPatch, app) -> None:
    monkeypatch.setattr(ikko_module, "get_running_powerpoint", lambda: app)
    monkeypatch.setattr(ikko_module, "get_active_presentation", lambda a: MagicMock())


# --- 対象範囲の判定 ---


def test_selection_shapes_used_when_selected(monkeypatch: pytest.MonkeyPatch) -> None:
    s1 = _make_com_shape(top=100.0, text="line1")
    s2 = _make_com_shape(top=118.0, text="line2")
    app = _make_app_with_shapes([], selection_type=_SELECTION_SHAPES)
    shape_range = app.ActiveWindow.Selection.ShapeRange
    shape_range.Count = 2
    shape_range.Item.side_effect = lambda i: [s1, s2][i - 1]
    _setup_running(monkeypatch, app)

    IkkoProcessor().run(_base_args(dry_run=True))

    app.ActiveWindow.View.Slide.Shapes.Item.assert_not_called()


def test_no_selection_uses_active_slide_shapes(monkeypatch: pytest.MonkeyPatch) -> None:
    s1 = _make_com_shape(top=100.0, text="line1")
    s2 = _make_com_shape(top=118.0, text="line2")
    app = _make_app_with_shapes([s1, s2], selection_type=_SELECTION_NONE)
    _setup_running(monkeypatch, app)

    IkkoProcessor().run(_base_args(dry_run=True))

    assert app.ActiveWindow.View.Slide.Shapes.Item.call_count == 2


# --- 対象シェイプの絞り込み ---


def test_shape_without_text_frame_excluded(monkeypatch: pytest.MonkeyPatch) -> None:
    no_tf = _make_com_shape(has_text_frame=False)
    s1 = _make_com_shape(top=100.0, text="line1")
    s2 = _make_com_shape(top=118.0, text="line2")
    app = _make_app_with_shapes([no_tf, s1, s2])
    _setup_running(monkeypatch, app)

    result = IkkoProcessor().run(_base_args())

    assert result == 0
    s1.Delete.assert_not_called()


def test_blank_text_shape_excluded(monkeypatch: pytest.MonkeyPatch) -> None:
    blank = _make_com_shape(text="   ")
    app = _make_app_with_shapes([blank])
    _setup_running(monkeypatch, app)

    result = IkkoProcessor().run(_base_args())
    assert result == 0


def test_multi_paragraph_shape_excluded(monkeypatch: pytest.MonkeyPatch) -> None:
    multi = _make_com_shape(top=100.0, paragraphs_count=2, text="already merged")
    single = _make_com_shape(top=118.0, text="line")
    app = _make_app_with_shapes([multi, single])
    _setup_running(monkeypatch, app)

    IkkoProcessor().run(_base_args())

    multi.Delete.assert_not_called()
    single.Delete.assert_not_called()  # 相手がいないので単独クラスタになり合体しない


# --- 合体処理 ---


def test_start_new_undo_entry_called_before_merge(monkeypatch: pytest.MonkeyPatch) -> None:
    s1 = _make_com_shape(top=100.0, text="line1")
    s2 = _make_com_shape(top=118.0, text="line2")
    app = _make_app_with_shapes([s1, s2])
    _setup_running(monkeypatch, app)

    IkkoProcessor().run(_base_args())

    app.StartNewUndoEntry.assert_called_once()


def test_merged_text_joined_with_cr_in_display_order(monkeypatch: pytest.MonkeyPatch) -> None:
    s1 = _make_com_shape(top=100.0, text="line1")
    s2 = _make_com_shape(top=118.0, text="line2")
    s3 = _make_com_shape(top=136.0, text="line3")
    app = _make_app_with_shapes([s3, s1, s2])  # 入力順はバラバラ
    _setup_running(monkeypatch, app)

    IkkoProcessor().run(_base_args())

    assert s1.TextFrame.TextRange.Text == "line1\rline2\rline3"


def test_non_head_shapes_deleted(monkeypatch: pytest.MonkeyPatch) -> None:
    s1 = _make_com_shape(top=100.0, text="line1")
    s2 = _make_com_shape(top=118.0, text="line2")
    app = _make_app_with_shapes([s1, s2])
    _setup_running(monkeypatch, app)

    IkkoProcessor().run(_base_args())

    s2.Delete.assert_called_once()
    s1.Delete.assert_not_called()


def test_head_shape_bounding_box_set(monkeypatch: pytest.MonkeyPatch) -> None:
    s1 = _make_com_shape(left=100.0, top=100.0, width=200.0, height=20.0, text="line1")
    s2 = _make_com_shape(left=100.0, top=118.0, width=180.0, height=20.0, text="line2")
    app = _make_app_with_shapes([s1, s2])
    _setup_running(monkeypatch, app)

    IkkoProcessor().run(_base_args())

    assert s1.Left == 100.0
    assert s1.Top == 100.0
    assert s1.Width == 200.0
    assert s1.Height == 38.0


def test_style_reapplied_after_text_set(monkeypatch: pytest.MonkeyPatch) -> None:
    style = {"font_name": "Meiryo", "font_size": 14.0, "bold": -1, "color": 255}
    s1 = _make_com_shape(top=100.0, text="line1", **style)
    s2 = _make_com_shape(top=118.0, text="line2", **style)
    app = _make_app_with_shapes([s1, s2])
    _setup_running(monkeypatch, app)

    IkkoProcessor().run(_base_args())

    assert s1.TextFrame.TextRange.Font.Name == "Meiryo"
    assert s1.TextFrame.TextRange.Font.Size == 14.0
    assert s1.TextFrame.TextRange.Font.Bold == -1
    assert s1.TextFrame.TextRange.Font.Color.RGB == 255


def test_singleton_cluster_not_merged(monkeypatch: pytest.MonkeyPatch) -> None:
    s1 = _make_com_shape(top=100.0, text="alone")
    app = _make_app_with_shapes([s1])
    _setup_running(monkeypatch, app)

    IkkoProcessor().run(_base_args())

    s1.Delete.assert_not_called()


# --- --dry-run ---


def test_dry_run_does_not_delete_or_modify(monkeypatch: pytest.MonkeyPatch) -> None:
    s1 = _make_com_shape(top=100.0, text="line1")
    s2 = _make_com_shape(top=118.0, text="line2")
    app = _make_app_with_shapes([s1, s2])
    _setup_running(monkeypatch, app)

    IkkoProcessor().run(_base_args(dry_run=True))

    s2.Delete.assert_not_called()
    assert s1.TextFrame.TextRange.Text == "line1"  # 変更されていない


def test_dry_run_does_not_call_start_new_undo_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    s1 = _make_com_shape(top=100.0, text="line1")
    s2 = _make_com_shape(top=118.0, text="line2")
    app = _make_app_with_shapes([s1, s2])
    _setup_running(monkeypatch, app)

    IkkoProcessor().run(_base_args(dry_run=True))

    app.StartNewUndoEntry.assert_not_called()


def test_dry_run_with_selection_scopes_and_stays_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    s1 = _make_com_shape(top=100.0, text="line1")
    s2 = _make_com_shape(top=118.0, text="line2")
    app = _make_app_with_shapes([], selection_type=_SELECTION_SHAPES)
    shape_range = app.ActiveWindow.Selection.ShapeRange
    shape_range.Count = 2
    shape_range.Item.side_effect = lambda i: [s1, s2][i - 1]
    _setup_running(monkeypatch, app)

    IkkoProcessor().run(_base_args(dry_run=True))

    app.ActiveWindow.View.Slide.Shapes.Item.assert_not_called()
    s2.Delete.assert_not_called()
    app.StartNewUndoEntry.assert_not_called()


def test_dry_run_prints_cluster_contents(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    s1 = _make_com_shape(top=100.0, text="line1")
    s2 = _make_com_shape(top=118.0, text="line2")
    app = _make_app_with_shapes([s1, s2])
    _setup_running(monkeypatch, app)

    IkkoProcessor().run(_base_args(dry_run=True))

    out = capsys.readouterr().out
    assert "line1" in out
    assert "line2" in out


# --- エラー処理 ---


def test_powerpoint_not_running_raises_without_new_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_not_running():
        raise PowerPointNotRunningError("not running")

    monkeypatch.setattr(ikko_module, "get_running_powerpoint", raise_not_running)
    dispatch = MagicMock()
    monkeypatch.setattr("win32com.client.Dispatch", dispatch, raising=False)

    with pytest.raises(SystemExit):
        IkkoProcessor().run(_base_args())

    dispatch.assert_not_called()


def test_no_active_presentation_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ikko_module, "get_running_powerpoint", lambda: MagicMock())

    def raise_no_active(app):
        raise NoActivePresentationError("no active")

    monkeypatch.setattr(ikko_module, "get_active_presentation", raise_no_active)

    with pytest.raises(SystemExit):
        IkkoProcessor().run(_base_args())


def test_zero_target_shapes_returns_success(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _make_app_with_shapes([])
    _setup_running(monkeypatch, app)

    result = IkkoProcessor().run(_base_args())

    assert result == 0


def test_zero_clusters_returns_success_with_hint(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    s1 = _make_com_shape(top=100.0, text="line1", font_name="Meiryo")
    s2 = _make_com_shape(top=118.0, text="line2", font_name="Arial")  # フォントが違うので合体しない
    app = _make_app_with_shapes([s1, s2])
    _setup_running(monkeypatch, app)

    result = IkkoProcessor().run(_base_args())

    assert result == 0
    out = capsys.readouterr().out
    assert "見つかりませんでした" in out


def test_com_exception_mentions_undo(monkeypatch: pytest.MonkeyPatch) -> None:
    s1 = _make_com_shape(top=100.0, text="line1")
    s2 = _make_com_shape(top=118.0, text="line2")
    s2.Delete.side_effect = RuntimeError("boom")
    app = _make_app_with_shapes([s1, s2])
    _setup_running(monkeypatch, app)

    with pytest.raises(SystemExit, match="Ctrl\\+Z"):
        IkkoProcessor().run(_base_args())
