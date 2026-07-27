import argparse
from unittest.mock import MagicMock

import pytest

from workpytools.common.powerpoint import NoActivePresentationError, PowerPointNotRunningError
from workpytools.processing import nagasa as nagasa_module
from workpytools.processing.nagasa import NagasaProcessor

_SELECTION_NONE = 0
_SELECTION_SHAPES = 2


def _base_args(**overrides: object) -> argparse.Namespace:
    return argparse.Namespace(**overrides)


def _make_shape(
    left: float,
    top: float,
    width: float,
    height: float,
    has_text_frame: bool = True,
    autosize: int = 1,
) -> MagicMock:
    shape = MagicMock()
    shape.Left = left
    shape.Top = top
    shape.Width = width
    shape.Height = height
    shape.HasTextFrame = has_text_frame
    shape.TextFrame.AutoSize = autosize
    return shape


def _make_app_with_selection(selected: list, selection_type: int = _SELECTION_SHAPES) -> MagicMock:
    app = MagicMock()
    app.ActiveWindow.Selection.Type = selection_type
    shape_range = app.ActiveWindow.Selection.ShapeRange
    shape_range.Count = len(selected)
    shape_range.Item.side_effect = lambda i: selected[i - 1]
    return app


def _setup_running(monkeypatch: pytest.MonkeyPatch, app: MagicMock) -> None:
    monkeypatch.setattr(nagasa_module, "get_running_powerpoint", lambda: app)
    monkeypatch.setattr(nagasa_module, "get_active_presentation", lambda a: MagicMock())


# --- 対象範囲の判定 ---


def test_two_or_more_shapes_targeted(monkeypatch: pytest.MonkeyPatch) -> None:
    s1 = _make_shape(0, 0, 50, 30)
    s2 = _make_shape(100, 0, 80, 60)
    app = _make_app_with_selection([s1, s2])
    _setup_running(monkeypatch, app)

    result = NagasaProcessor().run(_base_args())

    assert result == 0


def test_single_shape_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    s1 = _make_shape(0, 0, 50, 30)
    app = _make_app_with_selection([s1])
    _setup_running(monkeypatch, app)

    with pytest.raises(SystemExit):
        NagasaProcessor().run(_base_args())


def test_no_selection_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _make_app_with_selection([], selection_type=_SELECTION_NONE)
    _setup_running(monkeypatch, app)

    with pytest.raises(SystemExit):
        NagasaProcessor().run(_base_args())


# --- サイズ統一の計算 ---


def test_width_unified_to_max(monkeypatch: pytest.MonkeyPatch) -> None:
    s1 = _make_shape(0, 0, 50, 30)
    s2 = _make_shape(100, 0, 200, 30)
    s3 = _make_shape(200, 0, 80, 30)
    app = _make_app_with_selection([s1, s2, s3])
    _setup_running(monkeypatch, app)

    NagasaProcessor().run(_base_args())

    assert s1.Width == 200
    assert s2.Width == 200
    assert s3.Width == 200


def test_height_unified_to_max(monkeypatch: pytest.MonkeyPatch) -> None:
    s1 = _make_shape(0, 0, 50, 20)
    s2 = _make_shape(100, 0, 50, 90)
    app = _make_app_with_selection([s1, s2])
    _setup_running(monkeypatch, app)

    NagasaProcessor().run(_base_args())

    assert s1.Height == 90
    assert s2.Height == 90


def test_width_and_height_max_independent(monkeypatch: pytest.MonkeyPatch) -> None:
    # 幅の最大を出すシェイプと高さの最大を出すシェイプが別々でもよい
    s1 = _make_shape(0, 0, width=300, height=20)  # 幅最大
    s2 = _make_shape(100, 0, width=50, height=90)  # 高さ最大
    app = _make_app_with_selection([s1, s2])
    _setup_running(monkeypatch, app)

    NagasaProcessor().run(_base_args())

    assert s1.Width == 300
    assert s1.Height == 90
    assert s2.Width == 300
    assert s2.Height == 90


# --- 中心固定リサイズの計算 ---


def test_center_preserved_after_resize(monkeypatch: pytest.MonkeyPatch) -> None:
    s1 = _make_shape(left=100.0, top=200.0, width=50.0, height=30.0)
    s2 = _make_shape(left=300.0, top=200.0, width=150.0, height=90.0)
    original_center = (100.0 + 25.0, 200.0 + 15.0)
    app = _make_app_with_selection([s1, s2])
    _setup_running(monkeypatch, app)

    NagasaProcessor().run(_base_args())

    new_center = (s1.Left + s1.Width / 2, s1.Top + s1.Height / 2)
    assert new_center[0] == pytest.approx(original_center[0])
    assert new_center[1] == pytest.approx(original_center[1])


def test_already_max_size_shape_center_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    s1 = _make_shape(left=10.0, top=20.0, width=200.0, height=90.0)
    s2 = _make_shape(left=300.0, top=20.0, width=50.0, height=30.0)
    original_center = (10.0 + 100.0, 20.0 + 45.0)
    app = _make_app_with_selection([s1, s2])
    _setup_running(monkeypatch, app)

    NagasaProcessor().run(_base_args())

    new_center = (s1.Left + s1.Width / 2, s1.Top + s1.Height / 2)
    assert new_center[0] == pytest.approx(original_center[0])
    assert new_center[1] == pytest.approx(original_center[1])


# --- 自動調整（AutoSize）の無効化 ---


def test_autosize_disabled_before_resize(monkeypatch: pytest.MonkeyPatch) -> None:
    s1 = _make_shape(0, 0, 50, 30, autosize=1)
    s2 = _make_shape(100, 0, 80, 60, autosize=1)
    app = _make_app_with_selection([s1, s2])
    _setup_running(monkeypatch, app)

    NagasaProcessor().run(_base_args())

    assert s1.TextFrame.AutoSize == 0
    assert s2.TextFrame.AutoSize == 0


def test_autosize_skipped_for_shapes_without_text_frame(monkeypatch: pytest.MonkeyPatch) -> None:
    s1 = _make_shape(0, 0, 50, 30, has_text_frame=False)
    s2 = _make_shape(100, 0, 200, 90, has_text_frame=True, autosize=1)
    app = _make_app_with_selection([s1, s2])
    _setup_running(monkeypatch, app)

    result = NagasaProcessor().run(_base_args())

    assert result == 0
    assert s1.Width == 200  # HasTextFrame=Falseでもリサイズ自体は行われる
    assert s2.TextFrame.AutoSize == 0


# --- 変更されないものの確認 ---


def test_shape_count_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    s1 = _make_shape(0, 0, 50, 30)
    s2 = _make_shape(100, 0, 80, 60)
    app = _make_app_with_selection([s1, s2])
    _setup_running(monkeypatch, app)

    NagasaProcessor().run(_base_args())

    s1.Delete.assert_not_called()
    s2.Delete.assert_not_called()


# --- StartNewUndoEntry ---


def test_start_new_undo_entry_called(monkeypatch: pytest.MonkeyPatch) -> None:
    s1 = _make_shape(0, 0, 50, 30)
    s2 = _make_shape(100, 0, 80, 60)
    app = _make_app_with_selection([s1, s2])
    _setup_running(monkeypatch, app)

    NagasaProcessor().run(_base_args())

    app.StartNewUndoEntry.assert_called_once()


# --- エラー処理 ---


def test_powerpoint_not_running_raises_without_new_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_not_running():
        raise PowerPointNotRunningError("not running")

    monkeypatch.setattr(nagasa_module, "get_running_powerpoint", raise_not_running)
    dispatch = MagicMock()
    monkeypatch.setattr("win32com.client.Dispatch", dispatch, raising=False)

    with pytest.raises(SystemExit):
        NagasaProcessor().run(_base_args())

    dispatch.assert_not_called()


def test_no_active_presentation_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(nagasa_module, "get_running_powerpoint", lambda: MagicMock())

    def raise_no_active(app):
        raise NoActivePresentationError("no active")

    monkeypatch.setattr(nagasa_module, "get_active_presentation", raise_no_active)

    with pytest.raises(SystemExit):
        NagasaProcessor().run(_base_args())
