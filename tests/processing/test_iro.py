import argparse
from unittest.mock import MagicMock

import pytest

from workpytools.common.powerpoint import NoActivePresentationError, PowerPointNotRunningError
from workpytools.common.theme_colors import hex_to_ppt_rgb
from workpytools.processing import iro as iro_module
from workpytools.processing.iro import IroProcessor

_MSO_GROUP = 6
_MSO_TEXT_BOX = 17
_MSO_COLOR_TYPE_SCHEME = 2
_MSO_COLOR_TYPE_RGB = 1


def _base_args(**overrides: object) -> argparse.Namespace:
    defaults: dict[str, object] = {}
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _make_shapes_collection(shapes: list) -> MagicMock:
    collection = MagicMock()
    collection.Count = len(shapes)
    collection.Item.side_effect = lambda i: shapes[i - 1]
    return collection


def _make_color(
    color_type: int = _MSO_COLOR_TYPE_RGB, rgb: int = 0x000000
) -> MagicMock:
    color = MagicMock()
    color.Type = color_type
    color.RGB = rgb
    return color


def _make_shape(
    text: str = "hello",
    has_text_frame: bool = True,
    shape_type: int = _MSO_TEXT_BOX,
    group_items: list | None = None,
    fill_visible: bool = True,
    fill_color: MagicMock | None = None,
    line_visible: bool = True,
    line_color: MagicMock | None = None,
    font_color: MagicMock | None = None,
) -> MagicMock:
    shape = MagicMock()
    shape.Type = shape_type
    shape.HasTextFrame = has_text_frame
    shape.TextFrame.TextRange.Text = text
    shape.Fill.Visible = fill_visible
    shape.Fill.ForeColor = fill_color if fill_color is not None else _make_color()
    shape.Line.Visible = line_visible
    shape.Line.ForeColor = line_color if line_color is not None else _make_color()
    shape.TextFrame.TextRange.Font.Color = (
        font_color if font_color is not None else _make_color()
    )
    if group_items is not None:
        shape.GroupItems = _make_shapes_collection(group_items)
    return shape


def _make_presentation(
    slide_shapes_list: list[list], design_count: int = 1
) -> tuple[MagicMock, list[MagicMock]]:
    presentation = MagicMock()

    slides = []
    for shapes in slide_shapes_list:
        slide = MagicMock()
        slide.Shapes = _make_shapes_collection(shapes)
        slides.append(slide)
    presentation.Slides = _make_shapes_collection(slides)

    designs = [MagicMock() for _ in range(design_count)]
    for design in designs:
        color_scheme = design.SlideMaster.Theme.ThemeColorScheme
        color_items: dict[int, MagicMock] = {}

        def _item(index: int, _items: dict[int, MagicMock] = color_items) -> MagicMock:
            if index not in _items:
                _items[index] = _make_color()
            return _items[index]

        # ThemeColorSchemeはpywin32のダイナミックディスパッチ経由だと
        # .Item(index)という明示メソッド呼び出しの形が解決できず
        # AttributeErrorになる実機挙動があるため、実装はCOMの既定メンバー
        # 呼び出し color_scheme(index) を使う（iro.py参照）。モックも
        # それに合わせ、MagicMock自体の呼び出し（__call__）を差し替える。
        color_scheme.side_effect = _item

    presentation.Designs = _make_shapes_collection(designs)
    return presentation, designs


def _app_with_presentation(presentation: MagicMock) -> MagicMock:
    app = MagicMock()
    app.ActiveWindow.Presentation = presentation
    return app


def _setup_running(monkeypatch: pytest.MonkeyPatch, app: MagicMock) -> None:
    monkeypatch.setattr(iro_module, "get_running_powerpoint", lambda: app)
    monkeypatch.setattr(
        iro_module, "get_active_presentation", lambda a: a.ActiveWindow.Presentation
    )


# --- ステップ1: 独自色化 ---


def test_theme_color_fill_is_frozen_to_current_rgb(monkeypatch: pytest.MonkeyPatch) -> None:
    fill_color = _make_color(color_type=_MSO_COLOR_TYPE_SCHEME, rgb=0x123456)
    shape = _make_shape(fill_color=fill_color)
    presentation, _designs = _make_presentation(slide_shapes_list=[[shape]])
    app = _app_with_presentation(presentation)
    _setup_running(monkeypatch, app)

    IroProcessor().run(_base_args())

    assert shape.Fill.ForeColor.RGB == 0x123456


def test_theme_color_line_is_frozen(monkeypatch: pytest.MonkeyPatch) -> None:
    line_color = _make_color(color_type=_MSO_COLOR_TYPE_SCHEME, rgb=0xABCDEF)
    shape = _make_shape(line_color=line_color)
    presentation, _designs = _make_presentation(slide_shapes_list=[[shape]])
    app = _app_with_presentation(presentation)
    _setup_running(monkeypatch, app)

    IroProcessor().run(_base_args())

    assert shape.Line.ForeColor.RGB == 0xABCDEF


def test_theme_color_font_is_frozen(monkeypatch: pytest.MonkeyPatch) -> None:
    font_color = _make_color(color_type=_MSO_COLOR_TYPE_SCHEME, rgb=0x445566)
    shape = _make_shape(text="本文", font_color=font_color)
    presentation, _designs = _make_presentation(slide_shapes_list=[[shape]])
    app = _app_with_presentation(presentation)
    _setup_running(monkeypatch, app)

    IroProcessor().run(_base_args())

    assert shape.TextFrame.TextRange.Font.Color.RGB == 0x445566


def test_rgb_color_is_not_counted_as_frozen(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    shape = _make_shape(
        fill_color=_make_color(color_type=_MSO_COLOR_TYPE_RGB, rgb=0x111111)
    )
    presentation, _designs = _make_presentation(slide_shapes_list=[[shape]])
    app = _app_with_presentation(presentation)
    _setup_running(monkeypatch, app)

    result = IroProcessor().run(_base_args())

    assert result == 0
    out = capsys.readouterr().out
    assert "0件独自色化" in out


def test_invisible_fill_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    fill_color = _make_color(color_type=_MSO_COLOR_TYPE_SCHEME, rgb=0x222222)
    shape = _make_shape(fill_visible=False, fill_color=fill_color)
    presentation, _designs = _make_presentation(slide_shapes_list=[[shape]])
    app = _app_with_presentation(presentation)
    _setup_running(monkeypatch, app)

    result = IroProcessor().run(_base_args())

    assert result == 0
    # Visible=Falseならアクセス自体が行われないため、Typeはscheme色の
    # ままで変化しない（RGBの再代入によってTypeがRGB型に変わることはない）
    assert shape.Fill.ForeColor.Type == _MSO_COLOR_TYPE_SCHEME


def test_table_shape_fill_access_error_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    # 表（msoTable）シェイプは.Fill/.Lineプロパティへのアクセス自体が
    # COMレベルの例外（pywintypes.com_error、AttributeErrorではない）に
    # なることが実機で確認されている。getattr()の既定値フォールバックは
    # AttributeErrorしか吸収しないため、com_error等の他の例外でも
    # 独自色化の対象外としてスキップされ、run()全体がクラッシュしない
    # ことを確認する。
    shape = MagicMock(spec=["Type", "HasTextFrame", "Fill", "Line", "TextFrame"])
    shape.Type = _MSO_TEXT_BOX
    shape.HasTextFrame = False
    type(shape).Fill = property(lambda self: (_ for _ in ()).throw(RuntimeError("boom")))
    type(shape).Line = property(lambda self: (_ for _ in ()).throw(RuntimeError("boom")))
    presentation, _designs = _make_presentation(slide_shapes_list=[[shape]])
    app = _app_with_presentation(presentation)
    _setup_running(monkeypatch, app)

    result = IroProcessor().run(_base_args())

    assert result == 0


def test_blank_text_shape_font_color_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    shape = _make_shape(
        text="", font_color=_make_color(color_type=_MSO_COLOR_TYPE_SCHEME, rgb=0x333333)
    )
    presentation, _designs = _make_presentation(slide_shapes_list=[[shape]])
    app = _app_with_presentation(presentation)
    _setup_running(monkeypatch, app)

    result = IroProcessor().run(_base_args())

    assert result == 0


def test_group_items_recursed_into_for_freezing(monkeypatch: pytest.MonkeyPatch) -> None:
    inner_fill = _make_color(color_type=_MSO_COLOR_TYPE_SCHEME, rgb=0x999999)
    inner = _make_shape(fill_color=inner_fill)
    group = _make_shape(shape_type=_MSO_GROUP, has_text_frame=False, group_items=[inner])
    presentation, _designs = _make_presentation(slide_shapes_list=[[group]])
    app = _app_with_presentation(presentation)
    _setup_running(monkeypatch, app)

    IroProcessor().run(_base_args())

    assert inner.Fill.ForeColor.RGB == 0x999999


# --- ステップ2: テーマカラー変更 ---


def test_theme_accent_colors_set_to_new_palette(monkeypatch: pytest.MonkeyPatch) -> None:
    presentation, designs = _make_presentation(slide_shapes_list=[])
    app = _app_with_presentation(presentation)
    _setup_running(monkeypatch, app)

    IroProcessor().run(_base_args())

    color_scheme = designs[0].SlideMaster.Theme.ThemeColorScheme
    assert color_scheme(5).RGB == hex_to_ppt_rgb("#1E7145")
    assert color_scheme(10).RGB == hex_to_ppt_rgb("#BFBFBF")


def test_theme_colors_applied_to_all_designs(monkeypatch: pytest.MonkeyPatch) -> None:
    presentation, designs = _make_presentation(slide_shapes_list=[], design_count=2)
    app = _app_with_presentation(presentation)
    _setup_running(monkeypatch, app)

    IroProcessor().run(_base_args())

    for design in designs:
        color_scheme = design.SlideMaster.Theme.ThemeColorScheme
        assert color_scheme(5).RGB == hex_to_ppt_rgb("#1E7145")


def test_freeze_preserves_original_rgb_not_new_theme_color(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 独自色化が先に行われ、その時点ではまだ新テーマカラーに変わって
    # いないため、フリーズされる値は元のRGB(0x123456)であり、新テーマの
    # アクセント1(#1E7145)の値ではないことを確認する。もし実装の順序が
    # 逆（テーマ変更が先）だと、この値が新テーマ色に汚染されてしまう。
    fill_color = _make_color(color_type=_MSO_COLOR_TYPE_SCHEME, rgb=0x123456)
    shape = _make_shape(fill_color=fill_color)
    presentation, _designs = _make_presentation(slide_shapes_list=[[shape]])
    app = _app_with_presentation(presentation)
    _setup_running(monkeypatch, app)

    IroProcessor().run(_base_args())

    assert shape.Fill.ForeColor.RGB == 0x123456
    assert shape.Fill.ForeColor.RGB != hex_to_ppt_rgb("#1E7145")


# --- ステップ3: 既定書式の一時適用 ---


def test_default_shape_formats_applied_and_shapes_deleted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    presentation, _designs = _make_presentation(slide_shapes_list=[[]])
    slide = presentation.Slides.Item(1)

    rectangle = MagicMock()
    connector = MagicMock()
    textbox = MagicMock()
    slide.Shapes.AddShape.return_value = rectangle
    slide.Shapes.AddConnector.return_value = connector
    slide.Shapes.AddTextbox.return_value = textbox

    app = _app_with_presentation(presentation)
    _setup_running(monkeypatch, app)

    IroProcessor().run(_base_args())

    assert rectangle.Line.Weight == 1
    assert connector.Line.Weight == 2
    assert textbox.TextFrame.TextRange.Font.Size == 12
    rectangle.Delete.assert_called_once()
    connector.Delete.assert_called_once()
    textbox.Delete.assert_called_once()


def test_default_shape_command_bar_failure_produces_warning_but_succeeds(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    presentation, _designs = _make_presentation(slide_shapes_list=[[]])
    slide = presentation.Slides.Item(1)
    slide.Shapes.AddShape.return_value = MagicMock()
    slide.Shapes.AddConnector.return_value = MagicMock()
    slide.Shapes.AddTextbox.return_value = MagicMock()

    app = _app_with_presentation(presentation)
    app.CommandBars.FindControl.side_effect = RuntimeError("control not found")
    _setup_running(monkeypatch, app)

    result = IroProcessor().run(_base_args())

    assert result == 0
    out = capsys.readouterr().out
    assert "既定の図形として設定" in out


def test_default_shape_no_slides_skips_without_error(monkeypatch: pytest.MonkeyPatch) -> None:
    presentation, _designs = _make_presentation(slide_shapes_list=[])
    app = _app_with_presentation(presentation)
    _setup_running(monkeypatch, app)

    result = IroProcessor().run(_base_args())

    assert result == 0


# --- Undo ---


def test_start_new_undo_entry_called(monkeypatch: pytest.MonkeyPatch) -> None:
    presentation, _designs = _make_presentation(slide_shapes_list=[])
    app = _app_with_presentation(presentation)
    _setup_running(monkeypatch, app)

    IroProcessor().run(_base_args())

    app.StartNewUndoEntry.assert_called_once()


# --- エラー処理 ---


def test_powerpoint_not_running_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_not_running():
        raise PowerPointNotRunningError("not running")

    monkeypatch.setattr(iro_module, "get_running_powerpoint", raise_not_running)

    with pytest.raises(SystemExit):
        IroProcessor().run(_base_args())


def test_no_active_presentation_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(iro_module, "get_running_powerpoint", lambda: MagicMock())

    def raise_no_active(app: object) -> None:
        raise NoActivePresentationError("no active")

    monkeypatch.setattr(iro_module, "get_active_presentation", raise_no_active)

    with pytest.raises(SystemExit):
        IroProcessor().run(_base_args())


def test_com_exception_in_freeze_step_mentions_undo(monkeypatch: pytest.MonkeyPatch) -> None:
    presentation, _designs = _make_presentation(slide_shapes_list=[])

    class _RaisingSlides:
        @property
        def Count(self) -> int:  # noqa: N802
            raise RuntimeError("boom")

    presentation.Slides = _RaisingSlides()
    app = _app_with_presentation(presentation)
    _setup_running(monkeypatch, app)

    with pytest.raises(SystemExit, match="Ctrl\\+Z"):
        IroProcessor().run(_base_args())
