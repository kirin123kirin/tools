import argparse
from unittest.mock import MagicMock

import pytest
from PIL import Image

from workpytools.common.powerpoint import NoActivePresentationError, PowerPointNotRunningError
from workpytools.processing import bunkatsu as bunkatsu_module
from workpytools.processing.bunkatsu import BunkatsuProcessor

_SELECTION_NONE = 0
_SELECTION_SHAPES = 2
_MSO_PICTURE = 13
_MSO_RECTANGLE = 1


def _base_args(**overrides: object) -> argparse.Namespace:
    defaults: dict[str, object] = dict(
        distance_ratio=0.5, background_color_distance=20.0, dry_run=False
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _make_picture_shape(
    left: float = 10.0,
    top: float = 20.0,
    width: float = 300.0,
    height: float = 200.0,
    shape_type: int = _MSO_PICTURE,
    name: str = "Picture 1",
) -> MagicMock:
    shape = MagicMock()
    shape.Type = shape_type
    shape.Left = left
    shape.Top = top
    shape.Width = width
    shape.Height = height
    shape.Name = name
    return shape


def _make_app_with_selection(selected: list, selection_type: int = _SELECTION_SHAPES) -> MagicMock:
    app = MagicMock()
    app.ActiveWindow.Selection.Type = selection_type
    shape_range = app.ActiveWindow.Selection.ShapeRange
    shape_range.Count = len(selected)
    shape_range.Item.side_effect = lambda i: selected[i - 1]
    return app


def _setup_running(monkeypatch: pytest.MonkeyPatch, app: MagicMock) -> None:
    monkeypatch.setattr(bunkatsu_module, "get_running_powerpoint", lambda: app)
    monkeypatch.setattr(bunkatsu_module, "get_active_presentation", lambda a: MagicMock())


def _fake_export_writes_png(size: tuple[int, int] | None = None):
    """Fake for shape.Export(path, filter, scale_width, scale_height, mode).

    If `size` is None, honors the requested scale_width/scale_height (as
    bunkatsu now passes them) -- this is what most tests want, since it
    keeps the scale_x/scale_y math self-consistent. Pass an explicit `size`
    only when a test needs the exported pixel size to differ from what was
    requested.
    """

    def export(path: str, _filter: int, scale_width: int, scale_height: int, _mode: int) -> None:
        actual_size = size if size is not None else (scale_width, scale_height)
        Image.new("RGBA", actual_size, (255, 0, 0, 255)).save(path)

    return export


# --- 事前状態チェック ---


def test_powerpoint_not_running_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_not_running():
        raise PowerPointNotRunningError("not running")

    monkeypatch.setattr(bunkatsu_module, "get_running_powerpoint", raise_not_running)

    with pytest.raises(SystemExit):
        BunkatsuProcessor().run(_base_args())


def test_no_active_presentation_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    app = MagicMock()
    monkeypatch.setattr(bunkatsu_module, "get_running_powerpoint", lambda: app)

    def raise_no_presentation(_app):
        raise NoActivePresentationError("no presentation")

    monkeypatch.setattr(bunkatsu_module, "get_active_presentation", raise_no_presentation)

    with pytest.raises(SystemExit):
        BunkatsuProcessor().run(_base_args())


def test_no_selection_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _make_app_with_selection([], selection_type=_SELECTION_NONE)
    _setup_running(monkeypatch, app)

    with pytest.raises(SystemExit):
        BunkatsuProcessor().run(_base_args())


def test_multiple_shapes_selected_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    shapes = [_make_picture_shape(), _make_picture_shape()]
    app = _make_app_with_selection(shapes)
    _setup_running(monkeypatch, app)

    with pytest.raises(SystemExit):
        BunkatsuProcessor().run(_base_args())


def test_non_picture_shape_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    shape = _make_picture_shape(shape_type=_MSO_RECTANGLE)
    app = _make_app_with_selection([shape])
    _setup_running(monkeypatch, app)

    with pytest.raises(SystemExit):
        BunkatsuProcessor().run(_base_args())


# --- 分割ロジックとの連携 ---


def test_no_split_when_single_region_found(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    shape = _make_picture_shape()
    shape.Export.side_effect = _fake_export_writes_png()
    app = _make_app_with_selection([shape])
    _setup_running(monkeypatch, app)
    monkeypatch.setattr(bunkatsu_module, "split_regions", lambda img, **kwargs: [])

    result = BunkatsuProcessor().run(_base_args())

    assert result == 0
    shape.Delete.assert_not_called()
    captured = capsys.readouterr()
    assert "見つかりませんでした" in captured.out


def test_dry_run_does_not_modify_presentation(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    shape = _make_picture_shape()
    shape.Export.side_effect = _fake_export_writes_png()
    app = _make_app_with_selection([shape])
    _setup_running(monkeypatch, app)

    regions = [Image.new("RGBA", (40, 60), (0, 0, 0, 0)), Image.new("RGBA", (40, 60), (0, 0, 0, 0))]
    monkeypatch.setattr(bunkatsu_module, "split_regions", lambda img, **kwargs: regions)

    result = BunkatsuProcessor().run(_base_args(dry_run=True))

    assert result == 0
    shape.Delete.assert_not_called()
    app.StartNewUndoEntry.assert_not_called()
    captured = capsys.readouterr()
    assert "2個の領域" in captured.out


def test_split_replaces_shape_with_regions(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    shape = _make_picture_shape(left=10.0, top=20.0, width=300.0, height=200.0, name="Picture 1")
    shape.Export.side_effect = _fake_export_writes_png(size=(100, 60))
    slide = MagicMock()
    shape.Parent = slide
    app = _make_app_with_selection([shape])
    _setup_running(monkeypatch, app)

    region_a = Image.new("RGBA", (40, 60), (0, 0, 0, 0))
    region_a.info["offset_x"] = 0
    region_a.info["offset_y"] = 0
    region_b = Image.new("RGBA", (40, 60), (0, 0, 0, 0))
    region_b.info["offset_x"] = 60
    region_b.info["offset_y"] = 0
    monkeypatch.setattr(
        bunkatsu_module, "split_regions", lambda img, **kwargs: [region_a, region_b]
    )

    result = BunkatsuProcessor().run(_base_args())

    assert result == 0
    app.StartNewUndoEntry.assert_called_once()
    assert slide.Shapes.AddPicture.call_count == 2
    shape.Delete.assert_called_once()

    # AddPictureは位置引数で呼ぶ:
    # (FileName, LinkToFile, SaveWithDocument, Left, Top, Width, Height)
    first_call = slide.Shapes.AddPicture.call_args_list[0]
    assert first_call.args[1] is False  # LinkToFile
    assert first_call.args[2] is True  # SaveWithDocument
    assert first_call.args[3] == pytest.approx(10.0)  # Left: offset_x=0 -> 元のLeftそのまま
    assert first_call.args[4] == pytest.approx(20.0)  # Top
    assert first_call.args[5] == pytest.approx(40 * (300.0 / 100))  # Width
    assert first_call.args[6] == pytest.approx(60 * (200.0 / 60))  # Height

    second_call = slide.Shapes.AddPicture.call_args_list[1]
    # offset_x=60px * scale_x(=3.0pt/px) = 180pt を元のLeftに加算
    assert second_call.args[3] == pytest.approx(10.0 + 60 * (300.0 / 100))  # Left

    captured = capsys.readouterr()
    assert "2個の画像に分割しました" in captured.out


def test_export_requests_pixel_size_scaled_from_shape_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Export()はScaleWidth/ScaleHeightを省略するとスライド全体基準の
    # ピクセルサイズを返してしまい、shape.Width/Heightとの比率計算が
    # 崩れるため、shapeのポイントサイズから明示的に計算したピクセルサイズ
    # ・ExportMode(ppScaleXY)を渡していることを確認する
    shape = _make_picture_shape(width=300.0, height=200.0)
    export_calls = []

    def export(path, filt, scale_width, scale_height, mode):
        export_calls.append((filt, scale_width, scale_height, mode))
        Image.new("RGBA", (scale_width, scale_height), (255, 0, 0, 255)).save(path)

    shape.Export.side_effect = export
    slide = MagicMock()
    shape.Parent = slide
    app = _make_app_with_selection([shape])
    _setup_running(monkeypatch, app)
    monkeypatch.setattr(bunkatsu_module, "split_regions", lambda img, **kwargs: [])

    BunkatsuProcessor().run(_base_args())

    assert len(export_calls) == 1
    filt, scale_width, scale_height, mode = export_calls[0]
    assert filt == bunkatsu_module._PP_SHAPE_FORMAT_PNG
    assert mode == bunkatsu_module._PP_SCALE_XY
    # 要求したピクセルサイズがshapeのポイントサイズに正比例していること
    assert scale_width / scale_height == pytest.approx(300.0 / 200.0)


def test_com_error_wrapped_as_system_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    shape = _make_picture_shape()
    shape.Export.side_effect = _fake_export_writes_png()
    slide = MagicMock()
    shape.Parent = slide
    slide.Shapes.AddPicture.side_effect = RuntimeError("boom")
    app = _make_app_with_selection([shape])
    _setup_running(monkeypatch, app)

    regions = [Image.new("RGBA", (40, 60)), Image.new("RGBA", (40, 60))]
    monkeypatch.setattr(bunkatsu_module, "split_regions", lambda img, **kwargs: regions)

    with pytest.raises(SystemExit, match="Ctrl\\+Z"):
        BunkatsuProcessor().run(_base_args())
