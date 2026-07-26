import argparse
from unittest.mock import MagicMock

import pytest

from tools.common.powerpoint import NoActivePresentationError, PowerPointNotRunningError
from tools.processing import tbl as tbl_module
from tools.processing.tbl import TblProcessor

_SELECTION_NONE = 0
_SELECTION_SHAPES = 2


def _base_args(**overrides: object) -> argparse.Namespace:
    return argparse.Namespace(**overrides)


def _make_border(weight: float = 1.0, color: int = 0, visible: int = -1) -> MagicMock:
    border = MagicMock()
    border.Weight = weight
    border.ForeColor.RGB = color
    border.Visible = visible
    return border


def _make_cell(
    text: str = "cell",
    font_name: str = "Meiryo",
    font_size: float = 14.0,
    bold: int = 0,
    fill_visible: int = -1,
    fill_color: int = 0,
    border_weight: float = 1.0,
    border_color: int = 0,
    border_visible: int = -1,
) -> MagicMock:
    cell = MagicMock()
    cell_shape = cell.Shape
    cell_shape.TextFrame.TextRange.Text = text
    cell_shape.TextFrame.TextRange.Font.Name = font_name
    cell_shape.TextFrame.TextRange.Font.Size = font_size
    cell_shape.TextFrame.TextRange.Font.Bold = bold
    cell_shape.TextFrame.TextRange.Font.Color.RGB = 0
    cell_shape.TextFrame.TextRange.ParagraphFormat.Alignment = 1
    cell_shape.Fill.Visible = fill_visible
    cell_shape.Fill.ForeColor.RGB = fill_color
    cell.Borders.side_effect = lambda side: _make_border(
        border_weight, border_color, border_visible
    )
    return cell


def _make_table_shape(
    n_rows: int,
    n_cols: int,
    left: float = 50.0,
    top: float = 50.0,
    col_width: float = 100.0,
    row_height: float = 50.0,
    cell_factory=None,
) -> MagicMock:
    table_shape = MagicMock()
    table_shape.HasTable = True
    table_shape.Left = left
    table_shape.Top = top

    table = table_shape.Table
    table.Rows.Count = n_rows
    table.Columns.Count = n_cols
    table.Columns.side_effect = lambda c: MagicMock(Width=col_width)
    table.Rows.side_effect = lambda r: MagicMock(Height=row_height)

    cells = {}
    for r in range(1, n_rows + 1):
        for c in range(1, n_cols + 1):
            cells[(r, c)] = cell_factory(r, c) if cell_factory else _make_cell(text=f"R{r}C{c}")
    table.Cell.side_effect = lambda r, c: cells[(r, c)]

    slide = MagicMock()
    table_shape.Parent = slide
    return table_shape, slide


def _make_app_with_selection(selected: list, selection_type: int = _SELECTION_SHAPES) -> MagicMock:
    app = MagicMock()
    app.ActiveWindow.Selection.Type = selection_type
    shape_range = app.ActiveWindow.Selection.ShapeRange
    shape_range.Count = len(selected)
    shape_range.Item.side_effect = lambda i: selected[i - 1]
    return app


def _setup_running(monkeypatch: pytest.MonkeyPatch, app: MagicMock) -> None:
    monkeypatch.setattr(tbl_module, "get_running_powerpoint", lambda: app)
    monkeypatch.setattr(tbl_module, "get_active_presentation", lambda a: MagicMock())


# --- 方向の自動判定 ---


def test_selection_with_table_triggers_decompose(monkeypatch: pytest.MonkeyPatch) -> None:
    table_shape, slide = _make_table_shape(1, 1)
    app = _make_app_with_selection([table_shape])
    _setup_running(monkeypatch, app)

    TblProcessor().run(_base_args())

    table_shape.Delete.assert_called_once()


def test_two_non_table_shapes_trigger_compose(monkeypatch: pytest.MonkeyPatch) -> None:
    s1 = _make_rect_shape(left=0, top=0)
    s2 = _make_rect_shape(left=100, top=0)
    app = _make_app_with_selection([s1, s2])
    _setup_running(monkeypatch, app)

    TblProcessor().run(_base_args())

    s1.Parent.Shapes.AddTable.assert_called_once()


def test_single_multiline_shape_triggers_line_split(monkeypatch: pytest.MonkeyPatch) -> None:
    shape = _make_text_shape("行1\r行2")
    app = _make_app_with_selection([shape])
    _setup_running(monkeypatch, app)

    TblProcessor().run(_base_args())

    shape.Delete.assert_called_once()


def test_single_shape_no_text_does_nothing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    shape = MagicMock()
    shape.HasTable = False
    shape.HasTextFrame = False
    app = _make_app_with_selection([shape])
    _setup_running(monkeypatch, app)

    result = TblProcessor().run(_base_args())

    assert result == 0
    shape.Delete.assert_not_called()
    assert "対象" in capsys.readouterr().out


def test_single_shape_single_line_does_nothing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    shape = _make_text_shape("1行だけ")
    app = _make_app_with_selection([shape])
    _setup_running(monkeypatch, app)

    result = TblProcessor().run(_base_args())

    assert result == 0
    shape.Delete.assert_not_called()


def test_no_selection_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _make_app_with_selection([], selection_type=_SELECTION_NONE)
    _setup_running(monkeypatch, app)

    with pytest.raises(SystemExit):
        TblProcessor().run(_base_args())


# --- 分解方向 ---


def _make_rect_shape(
    left: float = 0.0,
    top: float = 0.0,
    width: float = 100.0,
    height: float = 50.0,
    text: str = "text",
) -> MagicMock:
    shape = MagicMock()
    shape.HasTable = False
    shape.HasTextFrame = True
    shape.Left = left
    shape.Top = top
    shape.Width = width
    shape.Height = height
    shape.TextFrame.TextRange.Text = text
    shape.TextFrame.TextRange.Font.Name = "Meiryo"
    shape.TextFrame.TextRange.Font.Size = 14.0
    shape.TextFrame.TextRange.Font.Bold = 0
    shape.TextFrame.TextRange.Font.Color.RGB = 0
    shape.Fill.Visible = -1
    shape.Fill.ForeColor.RGB = 0
    shape.Line.Weight = 1.0
    shape.Line.ForeColor.RGB = 0
    shape.Line.Visible = -1
    slide = MagicMock()
    shape.Parent = slide
    return shape


def _make_text_shape(text: str) -> MagicMock:
    shape = MagicMock()
    shape.HasTable = False
    shape.HasTextFrame = True
    shape.Left = 100.0
    shape.Top = 100.0
    shape.Width = 300.0
    shape.Height = 90.0

    text_range = shape.TextFrame.TextRange
    text_range.Text = text
    lines = text.split("\r")
    text_range.Lines.return_value.Count = len(lines)

    def get_line(i, count):
        line = MagicMock()
        raw = lines[i - 1]
        line.Text = raw + ("\r" if i < len(lines) else "")
        line.Font.Name = "Meiryo"
        line.Font.Size = 14.0
        line.Font.Bold = 0
        line.Font.Color.RGB = 0
        return line

    text_range.Lines.side_effect = lambda *a: get_line(*a) if a else text_range.Lines.return_value

    slide = MagicMock()
    shape.Parent = slide
    return shape


def test_decompose_creates_shape_per_cell(monkeypatch: pytest.MonkeyPatch) -> None:
    table_shape, slide = _make_table_shape(2, 3)
    app = _make_app_with_selection([table_shape])
    _setup_running(monkeypatch, app)

    TblProcessor().run(_base_args())

    assert slide.Shapes.AddShape.call_count == 6


def test_decompose_keeps_cell_size_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    table_shape, slide = _make_table_shape(1, 1, col_width=200.0, row_height=80.0)
    app = _make_app_with_selection([table_shape])
    _setup_running(monkeypatch, app)

    TblProcessor().run(_base_args())

    _, args, _kwargs = slide.Shapes.AddShape.mock_calls[0]
    assert args[3] == 200.0  # width
    assert args[4] == 80.0  # height


def test_decompose_adds_gap_between_cells(monkeypatch: pytest.MonkeyPatch) -> None:
    table_shape, slide = _make_table_shape(1, 2, left=50.0, col_width=100.0)
    app = _make_app_with_selection([table_shape])
    _setup_running(monkeypatch, app)

    TblProcessor().run(_base_args())

    calls = slide.Shapes.AddShape.mock_calls
    left0 = calls[0][1][1]
    left1 = calls[1][1][1]
    assert left0 == pytest.approx(55.0)  # 50 + gap(5.0)
    assert left1 - (left0 + 100.0) == pytest.approx(5.0)  # gap before col1


def test_decompose_copies_text_and_font(monkeypatch: pytest.MonkeyPatch) -> None:
    table_shape, slide = _make_table_shape(1, 1, cell_factory=lambda r, c: _make_cell(text="hello"))
    app = _make_app_with_selection([table_shape])
    _setup_running(monkeypatch, app)

    TblProcessor().run(_base_args())

    created_rect = slide.Shapes.AddShape.return_value
    assert created_rect.TextFrame.TextRange.Text == "hello"


def test_decompose_deletes_original_table(monkeypatch: pytest.MonkeyPatch) -> None:
    table_shape, slide = _make_table_shape(1, 1)
    app = _make_app_with_selection([table_shape])
    _setup_running(monkeypatch, app)

    TblProcessor().run(_base_args())

    table_shape.Delete.assert_called_once()


def test_multiple_tables_processed_in_selection_order(monkeypatch: pytest.MonkeyPatch) -> None:
    t1, slide1 = _make_table_shape(1, 1)
    t2, slide2 = _make_table_shape(1, 1)
    app = _make_app_with_selection([t1, t2])
    _setup_running(monkeypatch, app)

    TblProcessor().run(_base_args())

    t1.Delete.assert_called_once()
    t2.Delete.assert_called_once()


def test_uniform_borders_applied_directly(monkeypatch: pytest.MonkeyPatch) -> None:
    table_shape, slide = _make_table_shape(
        1, 1, cell_factory=lambda r, c: _make_cell(border_weight=3.0)
    )
    app = _make_app_with_selection([table_shape])
    _setup_running(monkeypatch, app)

    TblProcessor().run(_base_args())

    created_rect = slide.Shapes.AddShape.return_value
    assert created_rect.Line.Weight == 3.0


def test_non_uniform_borders_use_top_as_representative_and_warn(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def factory(r, c):
        cell = _make_cell()
        borders = [_make_border(weight=w) for w in [5.0, 1.0, 1.0, 1.0]]
        cell.Borders.side_effect = lambda side: borders[side - 1]
        return cell

    table_shape, slide = _make_table_shape(1, 1, cell_factory=factory)
    app = _make_app_with_selection([table_shape])
    _setup_running(monkeypatch, app)

    with caplog.at_level("WARNING"):
        TblProcessor().run(_base_args())

    created_rect = slide.Shapes.AddShape.return_value
    assert created_rect.Line.Weight == 5.0
    assert "罫線" in caplog.text


# --- 合成方向 ---


def test_compose_calls_add_table_with_estimated_grid(monkeypatch: pytest.MonkeyPatch) -> None:
    s1 = _make_rect_shape(left=0, top=0)
    s2 = _make_rect_shape(left=150, top=0)
    app = _make_app_with_selection([s1, s2])
    _setup_running(monkeypatch, app)

    TblProcessor().run(_base_args())

    s1.Parent.Shapes.AddTable.assert_called_once_with(1, 2, 0.0, 0.0, 250.0, 50.0)


def test_compose_copies_text_to_cells(monkeypatch: pytest.MonkeyPatch) -> None:
    s1 = _make_rect_shape(left=0, top=0, text="A")
    s2 = _make_rect_shape(left=150, top=0, text="B")
    app = _make_app_with_selection([s1, s2])
    _setup_running(monkeypatch, app)

    table_shape = s1.Parent.Shapes.AddTable.return_value
    cell_texts = {}

    def cell_side_effect(r, c):
        cell = MagicMock()
        cell_texts[(r, c)] = cell
        return cell

    table_shape.Table.Cell.side_effect = cell_side_effect

    TblProcessor().run(_base_args())

    assert cell_texts[(1, 1)].Shape.TextFrame.TextRange.Text == "A"
    assert cell_texts[(1, 2)].Shape.TextFrame.TextRange.Text == "B"


def test_compose_sets_column_widths_and_row_heights(monkeypatch: pytest.MonkeyPatch) -> None:
    s1 = _make_rect_shape(left=0, top=0, width=100, height=50)
    s2 = _make_rect_shape(left=150, top=0, width=200, height=50)
    app = _make_app_with_selection([s1, s2])
    _setup_running(monkeypatch, app)

    table_shape = s1.Parent.Shapes.AddTable.return_value

    TblProcessor().run(_base_args())

    table_shape.Table.Columns.assert_any_call(1)
    table_shape.Table.Columns.assert_any_call(2)


def test_compose_deletes_original_shapes(monkeypatch: pytest.MonkeyPatch) -> None:
    s1 = _make_rect_shape(left=0, top=0)
    s2 = _make_rect_shape(left=150, top=0)
    app = _make_app_with_selection([s1, s2])
    _setup_running(monkeypatch, app)

    TblProcessor().run(_base_args())

    s1.Delete.assert_called_once()
    s2.Delete.assert_called_once()


def test_compose_allows_uneven_gaps(monkeypatch: pytest.MonkeyPatch) -> None:
    s1 = _make_rect_shape(left=0, top=0)
    s2 = _make_rect_shape(left=120, top=0)
    s3 = _make_rect_shape(left=300, top=0)
    app = _make_app_with_selection([s1, s2, s3])
    _setup_running(monkeypatch, app)

    TblProcessor().run(_base_args())

    s1.Parent.Shapes.AddTable.assert_called_once()
    args = s1.Parent.Shapes.AddTable.call_args[0]
    assert args[0] == 1  # rows
    assert args[1] == 3  # cols


def test_compose_duplicate_grid_position_raises_without_side_effects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    s1 = _make_rect_shape(left=0, top=0)
    s2 = _make_rect_shape(left=0.2, top=0.2)
    app = _make_app_with_selection([s1, s2])
    _setup_running(monkeypatch, app)

    with pytest.raises(SystemExit):
        TblProcessor().run(_base_args())

    s1.Parent.Shapes.AddTable.assert_not_called()
    s1.Delete.assert_not_called()
    s2.Delete.assert_not_called()


def test_compose_includes_non_rectangle_shapes(monkeypatch: pytest.MonkeyPatch) -> None:
    textbox = _make_rect_shape(left=0, top=0)
    circle = _make_rect_shape(left=150, top=0)
    app = _make_app_with_selection([textbox, circle])
    _setup_running(monkeypatch, app)

    TblProcessor().run(_base_args())

    textbox.Delete.assert_called_once()
    circle.Delete.assert_called_once()


# --- 行分割方向 ---


def test_line_split_creates_shape_per_nonblank_line(monkeypatch: pytest.MonkeyPatch) -> None:
    shape = _make_text_shape("行1\r行2\r行3")
    app = _make_app_with_selection([shape])
    _setup_running(monkeypatch, app)

    TblProcessor().run(_base_args())

    assert shape.Parent.Shapes.AddTextbox.call_count == 3


def test_line_split_keeps_left_and_width(monkeypatch: pytest.MonkeyPatch) -> None:
    shape = _make_text_shape("行1\r行2")
    shape.Left = 42.0
    shape.Width = 250.0
    app = _make_app_with_selection([shape])
    _setup_running(monkeypatch, app)

    TblProcessor().run(_base_args())

    for call in shape.Parent.Shapes.AddTextbox.mock_calls:
        _, args, _kwargs = call
        assert args[1] == 42.0  # left
        assert args[3] == 250.0  # width


def test_line_split_adds_gap_between_lines(monkeypatch: pytest.MonkeyPatch) -> None:
    shape = _make_text_shape("行1\r行2")
    shape.Top = 100.0
    shape.Height = 40.0  # -> line_height=20.0, gap=1.0
    app = _make_app_with_selection([shape])
    _setup_running(monkeypatch, app)

    TblProcessor().run(_base_args())

    calls = shape.Parent.Shapes.AddTextbox.mock_calls
    top0 = calls[0][1][2]
    top1 = calls[1][1][2]
    assert top0 == pytest.approx(101.0)  # 100 + gap(1.0)
    assert top1 - (top0 + 20.0) == pytest.approx(1.0)


def test_line_split_copies_text_and_font(monkeypatch: pytest.MonkeyPatch) -> None:
    shape = _make_text_shape("行1\r行2")
    app = _make_app_with_selection([shape])
    _setup_running(monkeypatch, app)

    TblProcessor().run(_base_args())

    new_box = shape.Parent.Shapes.AddTextbox.return_value
    assert new_box.TextFrame.TextRange.Text == "行2"  # 最後に呼ばれたのは2行目


def test_line_split_skips_blank_lines(monkeypatch: pytest.MonkeyPatch) -> None:
    shape = _make_text_shape("行1\r\r行3")
    app = _make_app_with_selection([shape])
    _setup_running(monkeypatch, app)

    TblProcessor().run(_base_args())

    assert shape.Parent.Shapes.AddTextbox.call_count == 2


def test_line_split_deletes_original(monkeypatch: pytest.MonkeyPatch) -> None:
    shape = _make_text_shape("行1\r行2")
    app = _make_app_with_selection([shape])
    _setup_running(monkeypatch, app)

    TblProcessor().run(_base_args())

    shape.Delete.assert_called_once()


def test_line_split_single_line_no_add_or_delete(monkeypatch: pytest.MonkeyPatch) -> None:
    shape = _make_text_shape("1行だけ")
    app = _make_app_with_selection([shape])
    _setup_running(monkeypatch, app)

    TblProcessor().run(_base_args())

    shape.Parent.Shapes.AddTextbox.assert_not_called()
    shape.Delete.assert_not_called()


def test_line_split_no_text_no_op(monkeypatch: pytest.MonkeyPatch) -> None:
    shape = MagicMock()
    shape.HasTable = False
    shape.HasTextFrame = True
    shape.TextFrame.TextRange.Text = ""
    app = _make_app_with_selection([shape])
    _setup_running(monkeypatch, app)

    result = TblProcessor().run(_base_args())

    assert result == 0
    shape.Delete.assert_not_called()


# --- StartNewUndoEntry ---


def test_start_new_undo_entry_called_for_decompose(monkeypatch: pytest.MonkeyPatch) -> None:
    table_shape, slide = _make_table_shape(1, 1)
    app = _make_app_with_selection([table_shape])
    _setup_running(monkeypatch, app)

    TblProcessor().run(_base_args())

    app.StartNewUndoEntry.assert_called_once()


def test_start_new_undo_entry_called_for_compose(monkeypatch: pytest.MonkeyPatch) -> None:
    s1 = _make_rect_shape(left=0, top=0)
    s2 = _make_rect_shape(left=150, top=0)
    app = _make_app_with_selection([s1, s2])
    _setup_running(monkeypatch, app)

    TblProcessor().run(_base_args())

    app.StartNewUndoEntry.assert_called_once()


def test_start_new_undo_entry_called_for_line_split(monkeypatch: pytest.MonkeyPatch) -> None:
    shape = _make_text_shape("行1\r行2")
    app = _make_app_with_selection([shape])
    _setup_running(monkeypatch, app)

    TblProcessor().run(_base_args())

    app.StartNewUndoEntry.assert_called_once()


# --- エラー処理 ---


def test_powerpoint_not_running_raises_without_new_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_not_running():
        raise PowerPointNotRunningError("not running")

    monkeypatch.setattr(tbl_module, "get_running_powerpoint", raise_not_running)
    dispatch = MagicMock()
    monkeypatch.setattr("win32com.client.Dispatch", dispatch, raising=False)

    with pytest.raises(SystemExit):
        TblProcessor().run(_base_args())

    dispatch.assert_not_called()


def test_no_active_presentation_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tbl_module, "get_running_powerpoint", lambda: MagicMock())

    def raise_no_active(app):
        raise NoActivePresentationError("no active")

    monkeypatch.setattr(tbl_module, "get_active_presentation", raise_no_active)

    with pytest.raises(SystemExit):
        TblProcessor().run(_base_args())
