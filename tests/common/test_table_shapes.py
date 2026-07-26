import pytest

from tools.common.table_shapes import (
    DuplicateGridPositionError,
    GridShape,
    compute_spaced_positions,
    estimate_grid,
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
