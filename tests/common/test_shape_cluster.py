from tools.common.shape_cluster import ShapeInfo, cluster_shapes


def _shape(
    left: float = 100.0,
    top: float = 100.0,
    width: float = 200.0,
    height: float = 20.0,
    text: str = "line",
    font_name: str | None = "Meiryo",
    font_size: float | None = 14.0,
    bold: int | None = 0,
    color: int | None = 0,
    alignment: int | None = 1,
    ref: object = None,
) -> ShapeInfo:
    return ShapeInfo(
        left=left,
        top=top,
        width=width,
        height=height,
        text=text,
        font_name=font_name,
        font_size=font_size,
        bold=bold,
        color=color,
        alignment=alignment,
        ref=ref if ref is not None else object(),
    )


def test_matching_adjacent_shapes_form_one_cluster() -> None:
    shapes = [
        _shape(top=100.0, text="line1"),
        _shape(top=118.0, text="line2"),
    ]
    clusters = cluster_shapes(shapes)
    assert len(clusters) == 1
    assert len(clusters[0]) == 2


def test_different_font_name_splits_cluster() -> None:
    shapes = [
        _shape(top=100.0, font_name="Meiryo"),
        _shape(top=118.0, font_name="Arial"),
    ]
    clusters = cluster_shapes(shapes)
    assert len(clusters) == 2


def test_different_font_size_splits_cluster() -> None:
    shapes = [
        _shape(top=100.0, font_size=14.0),
        _shape(top=118.0, font_size=16.0),
    ]
    clusters = cluster_shapes(shapes)
    assert len(clusters) == 2


def test_different_bold_splits_cluster() -> None:
    shapes = [
        _shape(top=100.0, bold=0),
        _shape(top=118.0, bold=-1),
    ]
    clusters = cluster_shapes(shapes)
    assert len(clusters) == 2


def test_different_color_splits_cluster() -> None:
    shapes = [
        _shape(top=100.0, color=0),
        _shape(top=118.0, color=255),
    ]
    clusters = cluster_shapes(shapes)
    assert len(clusters) == 2


def test_left_beyond_tolerance_splits_cluster() -> None:
    shapes = [
        _shape(left=100.0, top=100.0),
        _shape(left=105.0, top=118.0),
    ]
    clusters = cluster_shapes(shapes, left_tolerance=1.0)
    assert len(clusters) == 2


def test_left_within_tolerance_merges() -> None:
    shapes = [
        _shape(left=100.0, top=100.0),
        _shape(left=100.5, top=118.0),
    ]
    clusters = cluster_shapes(shapes, left_tolerance=1.0)
    assert len(clusters) == 1


def test_line_step_below_min_ratio_splits_cluster() -> None:
    # フォントサイズ14に対し、行送りが小さすぎる（重なっている）
    shapes = [
        _shape(top=100.0, font_size=14.0),
        _shape(top=105.0, font_size=14.0),  # step=5, min=0.8*14=11.2
    ]
    clusters = cluster_shapes(shapes)
    assert len(clusters) == 2


def test_line_step_above_max_ratio_splits_cluster() -> None:
    shapes = [
        _shape(top=100.0, font_size=14.0),
        _shape(top=200.0, font_size=14.0),  # step=100, max=2.2*14=30.8
    ]
    clusters = cluster_shapes(shapes)
    assert len(clusters) == 2


def test_line_step_just_inside_boundaries_merges() -> None:
    # ちょうどの境界値は浮動小数点の丸め方向次第で実装のtop=0基準の引き算と
    # 一致しないことがあるため、境界のわずかに内側で「範囲内なら合体する」
    # ことだけを検証する（境界の丸め自体は実装の関心事ではない）。
    size = 14.0
    min_step = size * 0.8
    max_step = size * 2.2
    margin = 0.01

    shapes_min = [
        _shape(top=100.0, font_size=size),
        _shape(top=100.0 + min_step + margin, font_size=size),
    ]
    assert len(cluster_shapes(shapes_min)) == 1

    shapes_max = [
        _shape(top=100.0, font_size=size),
        _shape(top=100.0 + max_step - margin, font_size=size),
    ]
    assert len(cluster_shapes(shapes_max)) == 1


def test_missing_font_size_prevents_merge() -> None:
    shapes = [
        _shape(top=100.0, font_size=None),
        _shape(top=118.0, font_size=None),
    ]
    clusters = cluster_shapes(shapes)
    assert len(clusters) == 2


def test_input_order_does_not_affect_result() -> None:
    a = _shape(left=100.0, top=100.0, text="a")
    b = _shape(left=100.0, top=118.0, text="b")
    c = _shape(left=100.0, top=136.0, text="c")

    clusters_forward = cluster_shapes([a, b, c])
    clusters_reversed = cluster_shapes([c, b, a])

    forward_texts = [[s.text for s in cluster] for cluster in clusters_forward]
    reversed_texts = [[s.text for s in cluster] for cluster in clusters_reversed]
    assert forward_texts == reversed_texts == [["a", "b", "c"]]


def test_three_or_more_consecutive_shapes_form_one_cluster() -> None:
    shapes = [
        _shape(top=100.0, text="a"),
        _shape(top=118.0, text="b"),
        _shape(top=136.0, text="c"),
    ]
    clusters = cluster_shapes(shapes)
    assert len(clusters) == 1
    assert len(clusters[0]) == 3


def test_single_shape_forms_singleton_cluster() -> None:
    clusters = cluster_shapes([_shape()])
    assert len(clusters) == 1
    assert len(clusters[0]) == 1


def test_empty_input_returns_no_clusters() -> None:
    assert cluster_shapes([]) == []


def test_excluded_shape_between_two_does_not_bridge_cluster() -> None:
    # BをあらかじめWフィルタで除外した状態を模す
    # （A・Cのみを渡し、間隔が大きすぎるため別クラスタになることを確認）
    a = _shape(top=100.0, text="a")
    c = _shape(top=300.0, text="c")  # Bが除外された後、A-C間の行送りは範囲外になる
    clusters = cluster_shapes([a, c])
    assert len(clusters) == 2
