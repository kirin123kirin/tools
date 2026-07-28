import argparse
from unittest.mock import MagicMock

import pytest

from workpytools.common.powerpoint import NoActivePresentationError, PowerPointNotRunningError
from workpytools.processing import mfont as mfont_module
from workpytools.processing.mfont import MfontProcessor

_MSO_GROUP = 6
_MSO_TEXT_BOX = 17


def _base_args(**overrides: object) -> argparse.Namespace:
    defaults: dict[str, object] = {}
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _make_shapes_collection(shapes: list) -> MagicMock:
    collection = MagicMock()
    collection.Count = len(shapes)
    collection.Item.side_effect = lambda i: shapes[i - 1]
    return collection


def _make_shape(
    text: str = "hello",
    has_text_frame: bool = True,
    shape_type: int = _MSO_TEXT_BOX,
    group_items: list | None = None,
) -> MagicMock:
    shape = MagicMock()
    shape.Type = shape_type
    shape.HasTextFrame = has_text_frame
    shape.TextFrame.TextRange.Text = text
    if group_items is not None:
        shape.GroupItems = _make_shapes_collection(group_items)
    return shape


def _make_presentation(
    slide_shapes_list: list[list],
    master_shapes: list | None = None,
    layout_shapes_list: list[list] | None = None,
) -> MagicMock:
    presentation = MagicMock()

    slides = []
    for shapes in slide_shapes_list:
        slide = MagicMock()
        slide.Shapes = _make_shapes_collection(shapes)
        slides.append(slide)
    presentation.Slides = slides

    design = MagicMock()
    master = design.SlideMaster
    master.Shapes = _make_shapes_collection(master_shapes or [])

    layouts = []
    for shapes in layout_shapes_list or []:
        layout = MagicMock()
        layout.Shapes = _make_shapes_collection(shapes)
        layouts.append(layout)
    master.CustomLayouts = layouts

    presentation.Designs = [design]
    return presentation, design


def _setup_running(monkeypatch: pytest.MonkeyPatch, app: MagicMock) -> None:
    monkeypatch.setattr(mfont_module, "get_running_powerpoint", lambda: app)
    monkeypatch.setattr(
        mfont_module, "get_active_presentation", lambda a: a.ActiveWindow.Presentation
    )


def _app_with_presentation(presentation: MagicMock) -> MagicMock:
    app = MagicMock()
    app.ActiveWindow.Presentation = presentation
    return app


# --- テーマフォント ---


def test_theme_fonts_set_to_meiryo_far_east_only(monkeypatch: pytest.MonkeyPatch) -> None:
    presentation, design = _make_presentation(slide_shapes_list=[])
    app = _app_with_presentation(presentation)
    _setup_running(monkeypatch, app)

    MfontProcessor().run(_base_args())

    theme = design.SlideMaster.Theme
    assert theme.ThemeFontScheme.MajorFont.NameFarEast == "メイリオ"
    assert theme.ThemeFontScheme.MinorFont.NameFarEast == "メイリオ"


# --- マスター・レイアウト ---


def test_master_placeholder_font_updated(monkeypatch: pytest.MonkeyPatch) -> None:
    master_shape = _make_shape(text="タイトルプレースホルダー")
    presentation, _design = _make_presentation(
        slide_shapes_list=[], master_shapes=[master_shape]
    )
    app = _app_with_presentation(presentation)
    _setup_running(monkeypatch, app)

    MfontProcessor().run(_base_args())

    assert master_shape.TextFrame.TextRange.Font.NameFarEast == "メイリオ"


def test_layout_placeholder_font_updated(monkeypatch: pytest.MonkeyPatch) -> None:
    layout_shape = _make_shape(text="レイアウトのタイトル")
    presentation, _design = _make_presentation(
        slide_shapes_list=[], layout_shapes_list=[[layout_shape]]
    )
    app = _app_with_presentation(presentation)
    _setup_running(monkeypatch, app)

    MfontProcessor().run(_base_args())

    assert layout_shape.TextFrame.TextRange.Font.NameFarEast == "メイリオ"


# --- スライド上のシェイプ ---


def test_slide_shape_font_updated(monkeypatch: pytest.MonkeyPatch) -> None:
    shape = _make_shape(text="本文のテキスト")
    presentation, _design = _make_presentation(slide_shapes_list=[[shape]])
    app = _app_with_presentation(presentation)
    _setup_running(monkeypatch, app)

    MfontProcessor().run(_base_args())

    assert shape.TextFrame.TextRange.Font.NameFarEast == "メイリオ"


def test_multiple_slides_all_updated(monkeypatch: pytest.MonkeyPatch) -> None:
    shape1 = _make_shape(text="1枚目")
    shape2 = _make_shape(text="2枚目")
    presentation, _design = _make_presentation(slide_shapes_list=[[shape1], [shape2]])
    app = _app_with_presentation(presentation)
    _setup_running(monkeypatch, app)

    MfontProcessor().run(_base_args())

    assert shape1.TextFrame.TextRange.Font.NameFarEast == "メイリオ"
    assert shape2.TextFrame.TextRange.Font.NameFarEast == "メイリオ"


def test_shape_without_text_frame_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    shape = _make_shape(has_text_frame=False)
    presentation, _design = _make_presentation(slide_shapes_list=[[shape]])
    app = _app_with_presentation(presentation)
    _setup_running(monkeypatch, app)

    result = MfontProcessor().run(_base_args())

    assert result == 0
    # 属性へのFont.NameFarEast=値という代入が行われていなければ、
    # MagicMockの自動生成属性のままなので明示的な文字列にはならない
    assert shape.TextFrame.TextRange.Font.NameFarEast != "メイリオ"


def test_blank_text_shape_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    shape = _make_shape(text="")
    presentation, _design = _make_presentation(slide_shapes_list=[[shape]])
    app = _app_with_presentation(presentation)
    _setup_running(monkeypatch, app)

    MfontProcessor().run(_base_args())

    assert shape.TextFrame.TextRange.Font.NameFarEast != "メイリオ"


def test_latin_font_name_not_touched(monkeypatch: pytest.MonkeyPatch) -> None:
    shape = _make_shape(text="Text")
    presentation, _design = _make_presentation(slide_shapes_list=[[shape]])
    app = _app_with_presentation(presentation)
    _setup_running(monkeypatch, app)

    MfontProcessor().run(_base_args())

    assert shape.TextFrame.TextRange.Font.Name != "メイリオ"


# --- グループ内シェイプの再帰処理 ---


def test_group_items_recursed_into(monkeypatch: pytest.MonkeyPatch) -> None:
    inner = _make_shape(text="グループ内テキスト")
    group = _make_shape(shape_type=_MSO_GROUP, has_text_frame=False, group_items=[inner])
    presentation, _design = _make_presentation(slide_shapes_list=[[group]])
    app = _app_with_presentation(presentation)
    _setup_running(monkeypatch, app)

    MfontProcessor().run(_base_args())

    assert inner.TextFrame.TextRange.Font.NameFarEast == "メイリオ"


def test_nested_group_items_recursed_into(monkeypatch: pytest.MonkeyPatch) -> None:
    innermost = _make_shape(text="奥のテキスト")
    inner_group = _make_shape(
        shape_type=_MSO_GROUP, has_text_frame=False, group_items=[innermost]
    )
    outer_group = _make_shape(
        shape_type=_MSO_GROUP, has_text_frame=False, group_items=[inner_group]
    )
    presentation, _design = _make_presentation(slide_shapes_list=[[outer_group]])
    app = _app_with_presentation(presentation)
    _setup_running(monkeypatch, app)

    MfontProcessor().run(_base_args())

    assert innermost.TextFrame.TextRange.Font.NameFarEast == "メイリオ"


# --- Undo ---


def test_start_new_undo_entry_called(monkeypatch: pytest.MonkeyPatch) -> None:
    presentation, _design = _make_presentation(slide_shapes_list=[])
    app = _app_with_presentation(presentation)
    _setup_running(monkeypatch, app)

    MfontProcessor().run(_base_args())

    app.StartNewUndoEntry.assert_called_once()


# --- エラー処理 ---


def test_powerpoint_not_running_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_not_running():
        raise PowerPointNotRunningError("not running")

    monkeypatch.setattr(mfont_module, "get_running_powerpoint", raise_not_running)

    with pytest.raises(SystemExit):
        MfontProcessor().run(_base_args())


def test_no_active_presentation_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mfont_module, "get_running_powerpoint", lambda: MagicMock())

    def raise_no_active(app: object) -> None:
        raise NoActivePresentationError("no active")

    monkeypatch.setattr(mfont_module, "get_active_presentation", raise_no_active)

    with pytest.raises(SystemExit):
        MfontProcessor().run(_base_args())


def test_com_exception_mentions_undo(monkeypatch: pytest.MonkeyPatch) -> None:
    presentation, _design = _make_presentation(slide_shapes_list=[])

    class _RaisingDesigns:
        def __iter__(self) -> object:
            raise RuntimeError("boom")

    presentation.Designs = _RaisingDesigns()
    app = _app_with_presentation(presentation)
    _setup_running(monkeypatch, app)

    with pytest.raises(SystemExit, match="Ctrl\\+Z"):
        MfontProcessor().run(_base_args())
