import math

from workpytools.common.connector_sites import (
    SiteShape,
    nearest_site,
    nearest_site_pair,
    site_position,
)


def _shape(
    left: float = 0.0,
    top: float = 0.0,
    width: float = 100.0,
    height: float = 50.0,
    site_count: int = 4,
    ref: object = None,
) -> SiteShape:
    return SiteShape(
        left=left,
        top=top,
        width=width,
        height=height,
        site_count=site_count,
        ref=ref if ref is not None else object(),
    )


# --- site_position: 4サイト（四角形など） ---


def test_four_sites_are_top_left_bottom_right_in_order() -> None:
    shape = _shape(left=0, top=0, width=100, height=50, site_count=4)
    assert site_position(shape, 1) == (50.0, 0.0)  # 上辺の中央
    assert site_position(shape, 2) == (0.0, 25.0)  # 左辺の中央
    assert site_position(shape, 3) == (50.0, 50.0)  # 下辺の中央
    assert site_position(shape, 4) == (100.0, 25.0)  # 右辺の中央


def test_four_sites_respect_shape_offset() -> None:
    shape = _shape(left=200, top=300, width=80, height=40, site_count=4)
    assert site_position(shape, 1) == (240.0, 300.0)
    assert site_position(shape, 3) == (240.0, 340.0)


# --- site_position: 4サイト以外（円・三角形など） ---


def test_non_four_site_count_spreads_around_bounding_ellipse() -> None:
    # 8サイトの場合、上を起点に時計回りに45度ずつ配置される
    shape = _shape(left=0, top=0, width=100, height=100, site_count=8)
    x1, y1 = site_position(shape, 1)
    assert x1 == 50.0
    assert y1 == 0.0  # 上

    x3, y3 = site_position(shape, 3)
    assert math.isclose(x3, 100.0, abs_tol=1e-9)
    assert math.isclose(y3, 50.0, abs_tol=1e-9)  # 右


def test_non_four_site_count_uses_width_and_height_independently() -> None:
    # 幅と高さが異なる場合、円ではなく楕円状に分布する
    shape = _shape(left=0, top=0, width=200, height=50, site_count=8)
    x3, y3 = site_position(shape, 3)
    assert math.isclose(x3, 200.0, abs_tol=1e-9)  # 右端はwidth基準
    assert math.isclose(y3, 25.0, abs_tol=1e-9)  # 中心はheight基準


def test_three_site_count_does_not_raise() -> None:
    shape = _shape(site_count=3)
    for i in range(1, 4):
        site_position(shape, i)  # 例外にならないこと


# --- nearest_site ---


def test_nearest_site_picks_closest_across_shapes() -> None:
    left_shape = _shape(left=0, top=0, width=100, height=50, ref="left")
    right_shape = _shape(left=300, top=0, width=100, height=50, ref="right")

    # 右のシェイプの左辺(300, 25)のすぐ近くを指定する
    pick = nearest_site((305.0, 25.0), [left_shape, right_shape])

    assert pick is not None
    assert pick.shape.ref == "right"
    assert pick.site_index == 2  # 左辺


def test_nearest_site_picks_correct_site_within_one_shape() -> None:
    shape = _shape(left=0, top=0, width=100, height=50, ref="only")

    # 下辺の中央(50, 50)付近
    pick = nearest_site((50.0, 60.0), [shape])

    assert pick is not None
    assert pick.site_index == 3


def test_nearest_site_returns_none_for_empty_shapes() -> None:
    assert nearest_site((0.0, 0.0), []) is None


def test_nearest_site_distance_is_reported() -> None:
    shape = _shape(left=0, top=0, width=100, height=50)
    pick = nearest_site((50.0, -10.0), [shape])
    assert pick is not None
    assert math.isclose(pick.distance, 10.0, abs_tol=1e-9)  # 上辺の中央から10pt


def test_nearest_site_tie_keeps_first_candidate() -> None:
    # 2つのシェイプが完全に対称な位置にあり、距離が同じになるケース
    a = _shape(left=0, top=0, width=100, height=50, ref="a")
    b = _shape(left=200, top=0, width=100, height=50, ref="b")
    # (150, 25)はaの右辺(100,25)からもbの左辺(200,25)からも50離れている
    pick = nearest_site((150.0, 25.0), [a, b])
    assert pick is not None
    assert pick.shape.ref == "a"  # 先に見つかった方が選ばれる（決定的）


# --- nearest_site_pair ---


def test_nearest_site_pair_picks_facing_sides() -> None:
    left_shape = _shape(left=0, top=0, width=100, height=50)
    right_shape = _shape(left=300, top=0, width=100, height=50)

    begin_index, end_index = nearest_site_pair(left_shape, right_shape)

    assert begin_index == 4  # 左シェイプの右辺
    assert end_index == 2  # 右シェイプの左辺


def test_nearest_site_pair_for_vertically_stacked_shapes() -> None:
    top_shape = _shape(left=0, top=0, width=100, height=50)
    bottom_shape = _shape(left=0, top=200, width=100, height=50)

    begin_index, end_index = nearest_site_pair(top_shape, bottom_shape)

    assert begin_index == 3  # 上シェイプの下辺
    assert end_index == 1  # 下シェイプの上辺
