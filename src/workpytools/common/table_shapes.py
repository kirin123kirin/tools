from __future__ import annotations

from dataclasses import dataclass

GAP_RATIO = 0.05  # margin between decomposed shapes, as a fraction of cell size
GRID_TOLERANCE = 1.0  # points, same reasoning as ikko's LEFT_TOLERANCE


@dataclass(frozen=True)
class CellSpacing:
    """Cumulative left/top offset and unchanged width/height for one cell,
    after inserting a gap-ratio margin before each column/row."""

    left: float
    top: float
    width: float
    height: float


def compute_spaced_positions(
    sizes: list[float], gap_ratio: float = GAP_RATIO
) -> list[tuple[float, float]]:
    """For a sequence of column widths (or row heights), return
    (new_offset, gap_used) pairs computed with the cursor method: advance by
    this cell's gap, record the offset, then advance by its size.

    Offsets are relative to 0; callers add the table's own Left/Top.
    """
    cursor = 0.0
    result = []
    for size in sizes:
        gap = size * gap_ratio
        cursor += gap
        result.append((cursor, gap))
        cursor += size
    return result


@dataclass(frozen=True)
class GridShape:
    """A shape's geometry and a reference back to the underlying COM object
    (opaque to this module), used as input to grid estimation."""

    left: float
    top: float
    width: float
    height: float
    ref: object


@dataclass(frozen=True)
class GridPosition:
    row: int
    col: int
    shape: GridShape


class DuplicateGridPositionError(RuntimeError):
    """Raised when two or more shapes map to the same (row, col)."""


def estimate_grid(
    shapes: list[GridShape], tolerance: float = GRID_TOLERANCE
) -> tuple[list[GridPosition], int, int]:
    """Cluster shapes' Left values into columns and Top values into rows,
    independent of whether gaps between shapes are uniform.

    Returns (positions, row_count, col_count). Raises
    DuplicateGridPositionError if two shapes land on the same grid cell.
    """
    col_starts = _cluster_axis([s.left for s in shapes], tolerance)
    row_starts = _cluster_axis([s.top for s in shapes], tolerance)

    positions: list[GridPosition] = []
    seen: set[tuple[int, int]] = set()
    for shape in shapes:
        col = _index_of_cluster(shape.left, col_starts, tolerance)
        row = _index_of_cluster(shape.top, row_starts, tolerance)
        if (row, col) in seen:
            raise DuplicateGridPositionError(
                f"同じセル位置に複数のシェイプが重なっています (row={row}, col={col})"
            )
        seen.add((row, col))
        positions.append(GridPosition(row=row, col=col, shape=shape))

    return positions, len(row_starts), len(col_starts)


def _cluster_axis(values: list[float], tolerance: float) -> list[float]:
    """Sort and greedily chain-merge values within `tolerance` of the
    previous value, so a run like 0.0, 0.9, 1.8, 2.7 (each step within
    tolerance, but the ends 2.7 apart) becomes one cluster rather than
    splitting on absolute distance from the first member. This intentionally
    favors simplicity over guarding against chained drift, since a table's
    columns/rows are normally cleanly separated in practice.
    """
    ordered = sorted(values)
    clusters: list[float] = []
    for value in ordered:
        if not clusters or value - clusters[-1] > tolerance:
            clusters.append(value)
    return clusters


def _index_of_cluster(value: float, cluster_starts: list[float], tolerance: float) -> int:
    """Find which cluster `value` belongs to, using the same chained
    tolerance test as `_cluster_axis`: the closest cluster start at or
    below `value` within `tolerance`, falling back to nearest overall.
    """
    best_index = 0
    best_distance = abs(value - cluster_starts[0])
    for i, start in enumerate(cluster_starts):
        distance = abs(value - start)
        if distance < best_distance:
            best_distance = distance
            best_index = i
    return best_index


def column_and_row_sizes(
    positions: list[GridPosition], n_rows: int, n_cols: int
) -> tuple[list[float], list[float]]:
    """Per-column max width and per-row max height, taken only from shapes
    that actually landed in that column/row. A cell (row, col) can be a gap
    (no shape there) and still get a nonzero size from other shapes sharing
    its row or column; only a row/col with zero shapes anywhere in it would
    read 0.0, which can't happen here since estimate_grid only ever
    produces rows/columns backed by at least one real shape's coordinate.
    """
    col_width = [0.0] * n_cols
    row_height = [0.0] * n_rows
    for pos in positions:
        col_width[pos.col] = max(col_width[pos.col], pos.shape.width)
        row_height[pos.row] = max(row_height[pos.row], pos.shape.height)
    return col_width, row_height


def grid_centers(
    col_width: list[float], row_height: list[float], overall_left: float, overall_top: float
) -> tuple[list[float], list[float]]:
    """Center x/y of each column/row, laid out with the cursor method
    (no gap between cells -- sizes alone determine the pitch) starting at
    the grid's own top-left corner.
    """
    center_x = []
    cursor_x = overall_left
    for width in col_width:
        center_x.append(cursor_x + width / 2)
        cursor_x += width

    center_y = []
    cursor_y = overall_top
    for height in row_height:
        center_y.append(cursor_y + height / 2)
        cursor_y += height

    return center_x, center_y
