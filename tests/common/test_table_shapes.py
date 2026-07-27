import pytest

from workpytools.common.table_shapes import (
    DuplicateGridPositionError,
    GridShape,
    column_and_row_sizes,
    compute_spaced_positions,
    estimate_grid,
    grid_centers,
)

# --- compute_spaced_positions ---


def test_uniform_sizes_get_uniform_gaps() -> None:
    result = compute_spaced_positions([100.0, 100.0, 100.0], gap_ratio=0.05)
    offsets = [r[0] for r in result]
    gaps = [r[1] for r in result]
    assert gaps == [5.0, 5.0, 5.0]
    assert offsets == [5.0, 110.0, 215.0]


def test_varying_sizes_get_varying_gaps() -> None:
    result = compute_spaced_positions([100.0, 150.0, 120.0], gap_ratio=0.05)
    gaps = [r[1] for r in result]
    assert gaps == [5.0, 7.5, 6.0]


def test_adjacent_shapes_have_gap_between_them() -> None:
    sizes = [100.0, 150.0, 120.0]
    result = compute_spaced_positions(sizes, gap_ratio=0.05)
    for i in range(len(sizes) - 1):
        right_edge = result[i][0] + sizes[i]
        actual_gap = result[i + 1][0] - right_edge
        assert actual_gap == pytest.approx(result[i + 1][1])


def test_first_position_is_not_zero() -> None:
    result = compute_spaced_positions([100.0], gap_ratio=0.05)
    assert result[0][0] == 5.0


def test_empty_sizes_returns_empty() -> None:
    assert compute_spaced_positions([]) == []


# --- estimate_grid ---


def _shape(
    left: float,
    top: float,
    width: float = 100.0,
    height: float = 50.0,
    ref: object = None,
) -> GridShape:
    return GridShape(
        left=left, top=top, width=width, height=height, ref=ref if ref is not None else object()
    )


def test_perfect_grid_estimated_correctly() -> None:
    shapes = [
        _shape(0, 0), _shape(100, 0),
        _shape(0, 50), _shape(100, 50),
    ]
    positions, rows, cols = estimate_grid(shapes)
    assert rows == 2
    assert cols == 2
    assert len(positions) == 4


def test_positions_close_within_tolerance_cluster_together() -> None:
    # left=0.0と0.5は許容誤差以内で同じ列にまとまる（別々の行に置いて
    # 重複エラーにならないようにする）
    shapes = [
        _shape(0.0, 0.0),
        _shape(0.5, 60.0),
        _shape(100.0, 0.0),
    ]
    positions, rows, cols = estimate_grid(shapes, tolerance=1.0)
    assert cols == 2
    assert rows == 2


def test_duplicate_grid_position_raises() -> None:
    shapes = [
        _shape(0, 0),
        _shape(0.2, 0.2),  # same grid cell as above, within tolerance
    ]
    with pytest.raises(DuplicateGridPositionError):
        estimate_grid(shapes, tolerance=1.0)


def test_uneven_gaps_still_estimate_correct_grid() -> None:
    # 列間隔・行間隔が均等でなくても正しく推定できること
    shapes = [
        _shape(0, 0), _shape(120, 0), _shape(300, 0),
        _shape(0, 60), _shape(120, 60), _shape(300, 60),
    ]
    positions, rows, cols = estimate_grid(shapes)
    assert rows == 2
    assert cols == 3


def test_missing_cell_leaves_gap_in_positions() -> None:
    # 歯抜け: (row=0, col=1)に相当するシェイプがない
    shapes = [
        _shape(0, 0), _shape(100, 0),
        _shape(0, 50),
    ]
    positions, rows, cols = estimate_grid(shapes)
    assert rows == 2
    assert cols == 2
    assert len(positions) == 3
    filled = {(p.row, p.col) for p in positions}
    assert (1, 1) not in filled


def test_non_rectangle_shapes_included() -> None:
    shapes = [_shape(0, 0, ref="rect"), _shape(100, 0, ref="textbox")]
    positions, rows, cols = estimate_grid(shapes)
    refs = {p.shape.ref for p in positions}
    assert refs == {"rect", "textbox"}


# --- column_and_row_sizes ---


def test_column_size_is_max_width_in_that_column() -> None:
    shapes = [
        _shape(0, 0, width=50), _shape(100, 0, width=300),
        _shape(0, 50, width=200), _shape(100, 50, width=60),
    ]
    positions, rows, cols = estimate_grid(shapes)
    col_width, row_height = column_and_row_sizes(positions, rows, cols)
    assert col_width[0] == 200  # max(50, 200)
    assert col_width[1] == 300  # max(300, 60)


def test_row_size_is_max_height_in_that_row() -> None:
    shapes = [
        _shape(0, 0, height=30), _shape(100, 0, height=40),
        _shape(0, 50, height=90), _shape(100, 50, height=20),
    ]
    positions, rows, cols = estimate_grid(shapes)
    col_width, row_height = column_and_row_sizes(positions, rows, cols)
    assert row_height[0] == 40  # max(30, 40)
    assert row_height[1] == 90  # max(90, 20)


def test_sizes_are_independent_per_column_and_row() -> None:
    # 単一のグローバル最大値に統一されないこと（列・行ごとに独立）
    shapes = [
        _shape(0, 0, width=50, height=30),
        _shape(100, 0, width=300, height=30),  # 極端に大きい幅
        _shape(0, 50, width=50, height=30),
        _shape(100, 50, width=50, height=30),
    ]
    positions, rows, cols = estimate_grid(shapes)
    col_width, _ = column_and_row_sizes(positions, rows, cols)
    assert col_width[0] == 50
    assert col_width[1] == 300  # 他の列には影響しない


def test_missing_cell_gets_zero_size() -> None:
    # (row=1, col=1)が歯抜け。行1のサイズはcol0のシェイプ(height=50)から
    # 決まり、列1のサイズはrow0のシェイプ(width=100)から決まる
    shapes = [
        _shape(0, 0, width=100, height=20),
        _shape(100, 0, width=100, height=20),
        _shape(0, 50, width=50, height=50),
    ]
    positions, rows, cols = estimate_grid(shapes)
    col_width, row_height = column_and_row_sizes(positions, rows, cols)
    assert col_width[1] == 100.0  # row0のシェイプ由来（歯抜けのrow1には無い）
    assert row_height[1] == 50.0  # col0のシェイプ由来（歯抜けのcol1には無い）




# --- grid_centers ---


def test_grid_centers_no_gap_between_cells() -> None:
    col_width = [50.0, 300.0]
    row_height = [30.0]
    center_x, center_y = grid_centers(col_width, row_height, overall_left=0.0, overall_top=0.0)
    assert center_x == [25.0, 200.0]
    assert center_y == [15.0]


def test_grid_centers_sum_matches_overall_size() -> None:
    col_width = [50.0, 300.0, 120.0]
    row_height = [40.0, 90.0]
    overall_left, overall_top = 10.0, 20.0
    center_x, center_y = grid_centers(col_width, row_height, overall_left, overall_top)

    # 最後の列の中心 + 半分の幅 == overall_left + 全列幅の合計
    assert center_x[-1] + col_width[-1] / 2 == pytest.approx(overall_left + sum(col_width))
    assert center_y[-1] + row_height[-1] / 2 == pytest.approx(overall_top + sum(row_height))


def test_no_overlap_when_shape_sizes_vary_widely() -> None:
    # 極端にサイズが異なるシェイプが混在しても重ならないことの退行検知
    shapes = [
        _shape(0, 0, width=50, height=30),
        _shape(60, 0, width=50, height=30),
        _shape(120, 0, width=300, height=30),
    ]
    positions, rows, cols = estimate_grid(shapes)
    col_width, row_height = column_and_row_sizes(positions, rows, cols)
    center_x, center_y = grid_centers(col_width, row_height, overall_left=0.0, overall_top=0.0)

    new_lefts_rights = []
    for pos in positions:
        cx = center_x[pos.col]
        new_left = cx - pos.shape.width / 2
        new_right = new_left + pos.shape.width
        new_lefts_rights.append((pos.col, new_left, new_right))

    new_lefts_rights.sort(key=lambda t: t[0])
    for i in range(len(new_lefts_rights) - 1):
        assert new_lefts_rights[i][2] <= new_lefts_rights[i + 1][1] + 1e-9
