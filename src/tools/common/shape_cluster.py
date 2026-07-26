from __future__ import annotations

from dataclasses import dataclass

LEFT_TOLERANCE = 1.0  # points
LINE_STEP_MIN_RATIO = 0.8
LINE_STEP_MAX_RATIO = 2.2


@dataclass(frozen=True)
class ShapeInfo:
    """A text-carrying shape's geometry, style, and a reference back to the
    underlying COM shape object (opaque to this module -- clustering never
    touches it directly)."""

    left: float
    top: float
    width: float
    height: float
    text: str
    font_name: str | None
    font_size: float | None
    bold: int | None  # COM returns 0 / -1, not a Python bool
    color: int | None
    alignment: int | None
    ref: object


def cluster_shapes(
    shapes: list[ShapeInfo],
    left_tolerance: float = LEFT_TOLERANCE,
    line_step_min_ratio: float = LINE_STEP_MIN_RATIO,
    line_step_max_ratio: float = LINE_STEP_MAX_RATIO,
) -> list[list[ShapeInfo]]:
    """Group adjacent shapes that look like consecutive lines of one
    paragraph, sorted left-then-top so clustering is independent of input
    order.
    """
    ordered = sorted(shapes, key=lambda s: (s.left, s.top))
    if not ordered:
        return []

    clusters: list[list[ShapeInfo]] = [[ordered[0]]]

    for prev, curr in zip(ordered, ordered[1:], strict=False):
        if _same_cluster(prev, curr, left_tolerance, line_step_min_ratio, line_step_max_ratio):
            clusters[-1].append(curr)
        else:
            clusters.append([curr])

    return clusters


def _same_cluster(
    prev: ShapeInfo,
    curr: ShapeInfo,
    left_tolerance: float,
    line_step_min_ratio: float,
    line_step_max_ratio: float,
) -> bool:
    same_style = (
        prev.font_name == curr.font_name
        and prev.font_size == curr.font_size
        and prev.bold == curr.bold
        and prev.color == curr.color
    )
    same_left = abs(prev.left - curr.left) <= left_tolerance

    size = prev.font_size
    if not size:
        return False
    line_step = curr.top - prev.top
    step_ok = (size * line_step_min_ratio) <= line_step <= (size * line_step_max_ratio)

    return same_style and same_left and step_ok
