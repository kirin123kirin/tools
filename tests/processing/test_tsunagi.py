import argparse
from unittest.mock import MagicMock

import pytest

from workpytools.common.powerpoint import NoActivePresentationError, PowerPointNotRunningError
from workpytools.processing import tsunagi as tsunagi_module
from workpytools.processing.tsunagi import TsunagiProcessor

_SELECTION_NONE = 0
_SELECTION_SHAPES = 2
_MSO_TRUE = -1
_MSO_FALSE = 0
_MSO_CONNECTOR_STRAIGHT = 1


def _base_args(**overrides: object) -> argparse.Namespace:
    defaults: dict[str, object] = {}
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _make_shape(
    left: float = 0.0,
    top: float = 0.0,
    width: float = 100.0,
    height: float = 50.0,
    site_count: int = 4,
    name: str = "shape",
) -> MagicMock:
    shape = MagicMock()
    shape.Connector = _MSO_FALSE
    shape.Left = left
    shape.Top = top
    shape.Width = width
    shape.Height = height
    shape.ConnectionSiteCount = site_count
    shape._test_name = name
    return shape


def _make_connector(
    left: float = 0.0,
    top: float = 0.0,
    width: float = 50.0,
    height: float = 20.0,
    flipped_h: bool = False,
    flipped_v: bool = False,
) -> MagicMock:
    connector = MagicMock()
    connector.Connector = _MSO_TRUE
    connector.Left = left
    connector.Top = top
    connector.Width = width
    connector.Height = height
    connector.HorizontalFlip = _MSO_TRUE if flipped_h else _MSO_FALSE
    connector.VerticalFlip = _MSO_TRUE if flipped_v else _MSO_FALSE
    return connector


def _make_app_with_selection(selected: list, selection_type: int = _SELECTION_SHAPES) -> MagicMock:
    app = MagicMock()
    app.ActiveWindow.Selection.Type = selection_type
    shape_range = app.ActiveWindow.Selection.ShapeRange
    shape_range.Count = len(selected)
    shape_range.Item.side_effect = lambda i: selected[i - 1]
    return app


def _setup_running(monkeypatch: pytest.MonkeyPatch, app: MagicMock) -> None:
    monkeypatch.setattr(tsunagi_module, "get_running_powerpoint", lambda: app)
    monkeypatch.setattr(tsunagi_module, "get_active_presentation", lambda a: MagicMock())


# --- 動作の自動判定 ---


def test_connector_with_two_shapes_triggers_snap(monkeypatch: pytest.MonkeyPatch) -> None:
    connector = _make_connector(left=110, top=20, width=80, height=10)
    left_shape = _make_shape(left=0, top=0, width=100, height=50, name="left")
    right_shape = _make_shape(left=200, top=0, width=100, height=50, name="right")
    app = _make_app_with_selection([connector, left_shape, right_shape])
    _setup_running(monkeypatch, app)

    result = TsunagiProcessor().run(_base_args())

    assert result == 0
    connector.ConnectorFormat.BeginConnect.assert_called_once()
    connector.ConnectorFormat.EndConnect.assert_called_once()


def test_two_shapes_without_connector_triggers_create(monkeypatch: pytest.MonkeyPatch) -> None:
    left_shape = _make_shape(left=0, top=0, width=100, height=50)
    right_shape = _make_shape(left=300, top=0, width=100, height=50)
    app = _make_app_with_selection([left_shape, right_shape])
    _setup_running(monkeypatch, app)

    result = TsunagiProcessor().run(_base_args())

    assert result == 0
    app.ActiveWindow.View.Slide.Shapes.AddConnector.assert_called_once()


def test_connector_with_one_shape_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    connector = _make_connector()
    shape = _make_shape()
    app = _make_app_with_selection([connector, shape])
    _setup_running(monkeypatch, app)

    with pytest.raises(SystemExit, match="2つ以上"):
        TsunagiProcessor().run(_base_args())


def test_three_shapes_without_connector_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    shapes = [_make_shape(left=i * 200) for i in range(3)]
    app = _make_app_with_selection(shapes)
    _setup_running(monkeypatch, app)

    with pytest.raises(SystemExit, match="ちょうど2つ"):
        TsunagiProcessor().run(_base_args())


def test_no_selection_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _make_app_with_selection([], selection_type=_SELECTION_NONE)
    _setup_running(monkeypatch, app)

    with pytest.raises(SystemExit):
        TsunagiProcessor().run(_base_args())


def test_line_shape_without_connector_flag_is_not_treated_as_connector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Shape.TypeがmsoLineでもConnector=msoFalseなら単なる直線であり、
    # 接続できないためシェイプとして扱われる（この場合3つのシェイプ扱い）
    line = _make_shape(name="plain_line")  # Connector = msoFalse
    a = _make_shape(left=0)
    b = _make_shape(left=300)
    app = _make_app_with_selection([line, a, b])
    _setup_running(monkeypatch, app)

    with pytest.raises(SystemExit, match="ちょうど2つ"):
        TsunagiProcessor().run(_base_args())


# --- 吸着 ---


def test_snap_connects_each_end_to_nearest_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    # 左シェイプの右辺(100,25)と右シェイプの左辺(200,25)の間にコネクタを置く
    connector = _make_connector(left=110, top=20, width=80, height=10)
    left_shape = _make_shape(left=0, top=0, width=100, height=50, name="left")
    right_shape = _make_shape(left=200, top=0, width=100, height=50, name="right")
    app = _make_app_with_selection([connector, left_shape, right_shape])
    _setup_running(monkeypatch, app)

    TsunagiProcessor().run(_base_args())

    begin_args = connector.ConnectorFormat.BeginConnect.call_args[0]
    end_args = connector.ConnectorFormat.EndConnect.call_args[0]
    assert begin_args[0] is left_shape
    assert begin_args[1] == 4  # 左シェイプの右辺
    assert end_args[0] is right_shape
    assert end_args[1] == 2  # 右シェイプの左辺


def test_snap_processes_all_selected_connectors(monkeypatch: pytest.MonkeyPatch) -> None:
    c1 = _make_connector(left=110, top=20, width=80, height=10)
    c2 = _make_connector(left=110, top=40, width=80, height=10)
    left_shape = _make_shape(left=0, top=0, width=100, height=50)
    right_shape = _make_shape(left=200, top=0, width=100, height=50)
    app = _make_app_with_selection([c1, c2, left_shape, right_shape])
    _setup_running(monkeypatch, app)

    TsunagiProcessor().run(_base_args())

    c1.ConnectorFormat.BeginConnect.assert_called_once()
    c2.ConnectorFormat.BeginConnect.assert_called_once()


def test_snap_raises_when_both_ends_nearest_same_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 片方のシェイプのすぐ近くに孤立して置かれたコネクタ
    connector = _make_connector(left=10, top=10, width=5, height=5)
    near_shape = _make_shape(left=0, top=0, width=100, height=50, name="near")
    far_shape = _make_shape(left=2000, top=2000, width=100, height=50, name="far")
    app = _make_app_with_selection([connector, near_shape, far_shape])
    _setup_running(monkeypatch, app)

    with pytest.raises(SystemExit, match="同じシェイプ"):
        TsunagiProcessor().run(_base_args())

    connector.ConnectorFormat.BeginConnect.assert_not_called()


def test_snap_does_not_change_connector_line_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connector = _make_connector(left=110, top=20, width=80, height=10)
    left_shape = _make_shape(left=0, top=0, width=100, height=50)
    right_shape = _make_shape(left=200, top=0, width=100, height=50)
    app = _make_app_with_selection([connector, left_shape, right_shape])
    _setup_running(monkeypatch, app)

    TsunagiProcessor().run(_base_args())

    # 吸着モードでは線の見た目を一切変えない
    assert connector.Line.Weight != 2
    assert connector.Line.ForeColor.RGB != 0x000000


def test_snap_respects_horizontal_flip_for_endpoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # HorizontalFlipが真なら、始点は矩形の右側・終点は左側になる
    connector = _make_connector(left=110, top=20, width=80, height=10, flipped_h=True)
    left_shape = _make_shape(left=0, top=0, width=100, height=50, name="left")
    right_shape = _make_shape(left=200, top=0, width=100, height=50, name="right")
    app = _make_app_with_selection([connector, left_shape, right_shape])
    _setup_running(monkeypatch, app)

    TsunagiProcessor().run(_base_args())

    begin_args = connector.ConnectorFormat.BeginConnect.call_args[0]
    end_args = connector.ConnectorFormat.EndConnect.call_args[0]
    assert begin_args[0] is right_shape  # 反転しているので始点が右
    assert end_args[0] is left_shape


# --- 新規作成 ---


def test_create_uses_straight_connector(monkeypatch: pytest.MonkeyPatch) -> None:
    a = _make_shape(left=0, top=0, width=100, height=50)
    b = _make_shape(left=300, top=0, width=100, height=50)
    app = _make_app_with_selection([a, b])
    _setup_running(monkeypatch, app)

    TsunagiProcessor().run(_base_args())

    call_args = app.ActiveWindow.View.Slide.Shapes.AddConnector.call_args[0]
    assert call_args[0] == _MSO_CONNECTOR_STRAIGHT


def test_create_connects_facing_sites(monkeypatch: pytest.MonkeyPatch) -> None:
    a = _make_shape(left=0, top=0, width=100, height=50)
    b = _make_shape(left=300, top=0, width=100, height=50)
    app = _make_app_with_selection([a, b])
    new_connector = app.ActiveWindow.View.Slide.Shapes.AddConnector.return_value
    _setup_running(monkeypatch, app)

    TsunagiProcessor().run(_base_args())

    begin_args = new_connector.ConnectorFormat.BeginConnect.call_args[0]
    end_args = new_connector.ConnectorFormat.EndConnect.call_args[0]
    assert begin_args[0] is a
    assert begin_args[1] == 4  # aの右辺
    assert end_args[0] is b
    assert end_args[1] == 2  # bの左辺


def test_create_sets_black_2pt_line(monkeypatch: pytest.MonkeyPatch) -> None:
    a = _make_shape(left=0, top=0, width=100, height=50)
    b = _make_shape(left=300, top=0, width=100, height=50)
    app = _make_app_with_selection([a, b])
    new_connector = app.ActiveWindow.View.Slide.Shapes.AddConnector.return_value
    _setup_running(monkeypatch, app)

    TsunagiProcessor().run(_base_args())

    assert new_connector.Line.ForeColor.RGB == 0x000000
    assert new_connector.Line.Weight == 2


def test_create_uses_selection_order_for_direction(monkeypatch: pytest.MonkeyPatch) -> None:
    first = _make_shape(left=300, top=0, width=100, height=50, name="first")
    second = _make_shape(left=0, top=0, width=100, height=50, name="second")
    app = _make_app_with_selection([first, second])
    new_connector = app.ActiveWindow.View.Slide.Shapes.AddConnector.return_value
    _setup_running(monkeypatch, app)

    TsunagiProcessor().run(_base_args())

    begin_args = new_connector.ConnectorFormat.BeginConnect.call_args[0]
    assert begin_args[0] is first  # Item(1)が始点


# --- Undo ---


def test_start_new_undo_entry_called_for_snap(monkeypatch: pytest.MonkeyPatch) -> None:
    connector = _make_connector(left=110, top=20, width=80, height=10)
    a = _make_shape(left=0, top=0, width=100, height=50)
    b = _make_shape(left=200, top=0, width=100, height=50)
    app = _make_app_with_selection([connector, a, b])
    _setup_running(monkeypatch, app)

    TsunagiProcessor().run(_base_args())

    app.StartNewUndoEntry.assert_called_once()


def test_start_new_undo_entry_called_for_create(monkeypatch: pytest.MonkeyPatch) -> None:
    a = _make_shape(left=0, top=0, width=100, height=50)
    b = _make_shape(left=300, top=0, width=100, height=50)
    app = _make_app_with_selection([a, b])
    _setup_running(monkeypatch, app)

    TsunagiProcessor().run(_base_args())

    app.StartNewUndoEntry.assert_called_once()


# --- エラー処理 ---


def test_powerpoint_not_running_raises_without_new_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_not_running():
        raise PowerPointNotRunningError("not running")

    monkeypatch.setattr(tsunagi_module, "get_running_powerpoint", raise_not_running)
    dispatch = MagicMock()
    monkeypatch.setattr("win32com.client.Dispatch", dispatch, raising=False)

    with pytest.raises(SystemExit):
        TsunagiProcessor().run(_base_args())

    dispatch.assert_not_called()


def test_no_active_presentation_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tsunagi_module, "get_running_powerpoint", lambda: MagicMock())

    def raise_no_active(app: object) -> None:
        raise NoActivePresentationError("no active")

    monkeypatch.setattr(tsunagi_module, "get_active_presentation", raise_no_active)

    with pytest.raises(SystemExit):
        TsunagiProcessor().run(_base_args())


def test_com_exception_mentions_undo(monkeypatch: pytest.MonkeyPatch) -> None:
    connector = _make_connector(left=110, top=20, width=80, height=10)
    connector.ConnectorFormat.BeginConnect.side_effect = RuntimeError("boom")
    a = _make_shape(left=0, top=0, width=100, height=50)
    b = _make_shape(left=200, top=0, width=100, height=50)
    app = _make_app_with_selection([connector, a, b])
    _setup_running(monkeypatch, app)

    with pytest.raises(SystemExit, match="Ctrl\\+Z"):
        TsunagiProcessor().run(_base_args())
