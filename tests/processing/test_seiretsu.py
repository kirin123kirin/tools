import argparse
from unittest.mock import MagicMock

import pytest

from tools.common.powerpoint import NoActivePresentationError, PowerPointNotRunningError
from tools.processing import seiretsu as seiretsu_module
from tools.processing.seiretsu import SeiretsuProcessor

_SELECTION_NONE = 0
_SELECTION_SHAPES = 2


def _base_args(**overrides: object) -> argparse.Namespace:
    return argparse.Namespace(**overrides)


def _make_shape(left: float, top: float, width: float = 100.0, height: float = 50.0) -> MagicMock:
    shape = MagicMock()
    shape.Left = left
    shape.Top = top
    shape.Width = width
    shape.Height = height
    return shape


def _make_app_with_selection(selected: list, selection_type: int = _SELECTION_SHAPES) -> MagicMock:
    app = MagicMock()
    app.ActiveWindow.Selection.Type = selection_type
    shape_range = app.ActiveWindow.Selection.ShapeRange
    shape_range.Count = len(selected)
    shape_range.Item.side_effect = lambda i: selected[i - 1]
    return app


def _setup_running(monkeypatch: pytest.MonkeyPatch, app: MagicMock) -> None:
    monkeypatch.setattr(seiretsu_module, "get_running_powerpoint", lambda: app)
    monkeypatch.setattr(seiretsu_module, "get_active_presentation", lambda a: MagicMock())


# --- 対象範囲の判定 ---


def test_two_or_more_shapes_all_targeted(monkeypatch: pytest.MonkeyPatch) -> None:
    s1 = _make_shape(0, 0)
    s2 = _make_shape(150, 0)
    app = _make_app_with_selection([s1, s2])
    _setup_running(monkeypatch, app)

    result = SeiretsuProcessor().run(_base_args())

    assert result == 0


def test_single_shape_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    s1 = _make_shape(0, 0)
    app = _make_app_with_selection([s1])
    _setup_running(monkeypatch, app)

    with pytest.raises(SystemExit):
        SeiretsuProcessor().run(_base_args())


def test_no_selection_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _make_app_with_selection([], selection_type=_SELECTION_NONE)
    _setup_running(monkeypatch, app)

    with pytest.raises(SystemExit):
        SeiretsuProcessor().run(_base_args())


# --- グリッド推定・セルサイズ ---


def test_grid_dimensions_estimated_correctly(monkeypatch: pytest.MonkeyPatch) -> None:
    shapes = [
        _make_shape(0, 0), _make_shape(150, 0),
        _make_shape(0, 80), _make_shape(150, 80),
    ]
    app = _make_app_with_selection(shapes)
    _setup_running(monkeypatch, app)

    result = SeiretsuProcessor().run(_base_args())

    assert result == 0


def test_uneven_gaps_still_align(monkeypatch: pytest.MonkeyPatch) -> None:
    shapes = [_make_shape(0, 0), _make_shape(120, 0), _make_shape(300, 0)]
    app = _make_app_with_selection(shapes)
    _setup_running(monkeypatch, app)

    SeiretsuProcessor().run(_base_args())

    # 全シェイプが何らかの新しい位置に書き換わっていること
    for s in shapes:
        assert isinstance(s.Left, float)


def test_missing_grid_cell_does_not_abort(monkeypatch: pytest.MonkeyPatch) -> None:
    shapes = [_make_shape(0, 0), _make_shape(150, 0), _make_shape(0, 80)]
    app = _make_app_with_selection(shapes)
    _setup_running(monkeypatch, app)

    result = SeiretsuProcessor().run(_base_args())

    assert result == 0


def test_duplicate_grid_position_raises_without_moving(monkeypatch: pytest.MonkeyPatch) -> None:
    s1 = _make_shape(0, 0)
    s2 = _make_shape(0.2, 0.2)
    original_left, original_top = s2.Left, s2.Top
    app = _make_app_with_selection([s1, s2])
    _setup_running(monkeypatch, app)

    with pytest.raises(SystemExit):
        SeiretsuProcessor().run(_base_args())

    assert s2.Left == original_left
    assert s2.Top == original_top


# --- 重心配置の計算 ---


def test_shape_center_matches_grid_center(monkeypatch: pytest.MonkeyPatch) -> None:
    # 単一列・単一行なら中心はそのままのはず
    s1 = _make_shape(left=10.0, top=20.0, width=100.0, height=50.0)
    s2 = _make_shape(left=200.0, top=20.0, width=100.0, height=50.0)
    app = _make_app_with_selection([s1, s2])
    _setup_running(monkeypatch, app)

    SeiretsuProcessor().run(_base_args())

    # 列0のシェイプはs1のみなのでcol_width=100、中心は overall_left + 50
    assert s1.Left + s1.Width / 2 == pytest.approx(10.0 + 50.0)


def test_shape_width_height_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    s1 = _make_shape(0, 0, width=80.0, height=40.0)
    s2 = _make_shape(150, 0, width=120.0, height=60.0)
    app = _make_app_with_selection([s1, s2])
    _setup_running(monkeypatch, app)

    SeiretsuProcessor().run(_base_args())

    assert s1.Width == 80.0
    assert s1.Height == 40.0
    assert s2.Width == 120.0
    assert s2.Height == 60.0


def test_overall_top_left_matches_original(monkeypatch: pytest.MonkeyPatch) -> None:
    # 左上（最小Left・最小Top）は元の配置と一致する。右端・下端は
    # 列・行サイズの合計で決まるため元の外接矩形とは一致しなくてよい
    # （doc/seiretsu.md「起点は揃えるが、全体サイズは外接矩形と
    # 一致させない」）
    s1 = _make_shape(left=0.0, top=0.0, width=50.0, height=30.0)
    s2 = _make_shape(left=60.0, top=0.0, width=50.0, height=30.0)
    s3 = _make_shape(left=120.0, top=0.0, width=300.0, height=30.0)
    app = _make_app_with_selection([s1, s2, s3])
    _setup_running(monkeypatch, app)

    original_left = min(s.Left for s in [s1, s2, s3])
    original_top = min(s.Top for s in [s1, s2, s3])

    SeiretsuProcessor().run(_base_args())

    new_left = min(s.Left for s in [s1, s2, s3])
    new_top = min(s.Top for s in [s1, s2, s3])
    assert new_left == pytest.approx(original_left)
    assert new_top == pytest.approx(original_top)


def test_no_overlap_with_widely_varying_sizes(monkeypatch: pytest.MonkeyPatch) -> None:
    s1 = _make_shape(left=0.0, top=0.0, width=50.0, height=30.0)
    s2 = _make_shape(left=60.0, top=0.0, width=50.0, height=30.0)
    s3 = _make_shape(left=120.0, top=0.0, width=300.0, height=30.0)
    app = _make_app_with_selection([s1, s2, s3])
    _setup_running(monkeypatch, app)

    SeiretsuProcessor().run(_base_args())

    shapes_sorted = sorted([s1, s2, s3], key=lambda s: s.Left)
    for i in range(len(shapes_sorted) - 1):
        right_edge = shapes_sorted[i].Left + shapes_sorted[i].Width
        assert right_edge <= shapes_sorted[i + 1].Left + 1e-6


# --- 変更されないものの確認 ---


def test_shape_count_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    s1 = _make_shape(0, 0)
    s2 = _make_shape(150, 0)
    app = _make_app_with_selection([s1, s2])
    _setup_running(monkeypatch, app)

    SeiretsuProcessor().run(_base_args())

    s1.Delete.assert_not_called()
    s2.Delete.assert_not_called()


# --- StartNewUndoEntry ---


def test_start_new_undo_entry_called(monkeypatch: pytest.MonkeyPatch) -> None:
    s1 = _make_shape(0, 0)
    s2 = _make_shape(150, 0)
    app = _make_app_with_selection([s1, s2])
    _setup_running(monkeypatch, app)

    SeiretsuProcessor().run(_base_args())

    app.StartNewUndoEntry.assert_called_once()


# --- エラー処理 ---


def test_powerpoint_not_running_raises_without_new_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_not_running():
        raise PowerPointNotRunningError("not running")

    monkeypatch.setattr(seiretsu_module, "get_running_powerpoint", raise_not_running)
    dispatch = MagicMock()
    monkeypatch.setattr("win32com.client.Dispatch", dispatch, raising=False)

    with pytest.raises(SystemExit):
        SeiretsuProcessor().run(_base_args())

    dispatch.assert_not_called()


def test_no_active_presentation_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(seiretsu_module, "get_running_powerpoint", lambda: MagicMock())

    def raise_no_active(app):
        raise NoActivePresentationError("no active")

    monkeypatch.setattr(seiretsu_module, "get_active_presentation", raise_no_active)

    with pytest.raises(SystemExit):
        SeiretsuProcessor().run(_base_args())
