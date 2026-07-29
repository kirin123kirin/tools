from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class SiteShape:
    """A shape's bounding box, connection site count, and a reference back
    to the underlying COM object (opaque to this module)."""

    left: float
    top: float
    width: float
    height: float
    site_count: int
    ref: object


@dataclass(frozen=True)
class SitePick:
    """One chosen connection site: which shape, which 1-based site index,
    and how far it was from the point we were matching against."""

    shape: SiteShape
    site_index: int
    distance: float


def site_position(shape: SiteShape, site_index: int) -> tuple[float, float]:
    """Approximate the (x, y) of a shape's 1-based connection site.

    PowerPoint exposes `ConnectionSiteCount` but no way to read a site's
    coordinates, so we derive them from the bounding box. For the common
    4-site case (rectangles, rounded rectangles, most basic shapes)
    PowerPoint numbers the sites top, left, bottom, right -- reproduced
    exactly here. Other counts are approximated by spreading the sites
    evenly around the bounding ellipse, starting at the top and going
    clockwise. The approximation is only used to rank sites by distance,
    where being slightly off rarely changes which site is nearest.
    """
    center_x = shape.left + shape.width / 2
    center_y = shape.top + shape.height / 2

    if shape.site_count == 4:
        positions = [
            (center_x, shape.top),  # 1: 上辺の中央
            (shape.left, center_y),  # 2: 左辺の中央
            (center_x, shape.top + shape.height),  # 3: 下辺の中央
            (shape.left + shape.width, center_y),  # 4: 右辺の中央
        ]
        return positions[site_index - 1]

    angle = math.radians(-90 + 360 * (site_index - 1) / shape.site_count)
    return (
        center_x + math.cos(angle) * shape.width / 2,
        center_y + math.sin(angle) * shape.height / 2,
    )


def nearest_site(point: tuple[float, float], shapes: list[SiteShape]) -> SitePick | None:
    """The connection site closest to `point` across every shape. Ties keep
    the first candidate found, so the result is deterministic. Returns None
    if `shapes` is empty or none of them has a connection site."""
    best: SitePick | None = None
    for shape in shapes:
        for site_index in range(1, shape.site_count + 1):
            x, y = site_position(shape, site_index)
            distance = math.hypot(point[0] - x, point[1] - y)
            if best is None or distance < best.distance:
                best = SitePick(shape=shape, site_index=site_index, distance=distance)
    return best


def nearest_site_pair(
    begin_shape: SiteShape, end_shape: SiteShape
) -> tuple[int, int]:
    """The pair of 1-based site indexes (one per shape) whose positions are
    closest to each other -- used when creating a brand new connector
    between two shapes, where there's no existing endpoint to match."""
    best: tuple[int, int] | None = None
    best_distance = math.inf
    for begin_index in range(1, begin_shape.site_count + 1):
        bx, by = site_position(begin_shape, begin_index)
        for end_index in range(1, end_shape.site_count + 1):
            ex, ey = site_position(end_shape, end_index)
            distance = math.hypot(bx - ex, by - ey)
            if distance < best_distance:
                best_distance = distance
                best = (begin_index, end_index)
    assert best is not None  # site_countは常に1以上のため必ず候補が見つかる
    return best
