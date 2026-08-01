from PIL import Image, ImageDraw

from workpytools.common.watershed import split_regions


def _two_separate_circles() -> Image.Image:
    img = Image.new("RGBA", (300, 150), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((20, 20, 120, 120), fill=(255, 0, 0, 255))
    draw.ellipse((150, 30, 260, 130), fill=(0, 0, 255, 255))
    return img


def _single_circle() -> Image.Image:
    img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((10, 10, 90, 90), fill=(0, 200, 0, 255))
    return img


def _fully_transparent() -> Image.Image:
    return Image.new("RGBA", (50, 50), (0, 0, 0, 0))


def _two_filled_circles_opaque_white_background() -> Image.Image:
    img = Image.new("RGBA", (300, 150), (255, 255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.ellipse((20, 20, 120, 120), fill=(255, 0, 0, 255))
    draw.ellipse((150, 30, 260, 130), fill=(0, 0, 255, 255))
    return img


def _two_outline_only_rounded_rectangles() -> Image.Image:
    # 塗りつぶしなし（線のみ）の図形。PowerPointの図形（オートシェイプ）を
    # 「塗りつぶしなし」設定でエクスポートした場合を想定
    img = Image.new("RGBA", (500, 200), (255, 255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((20, 20, 200, 170), radius=15, outline=(0, 0, 0, 255), width=2)
    draw.rounded_rectangle((300, 20, 480, 170), radius=15, outline=(0, 0, 0, 255), width=2)
    return img


def _two_pale_filled_rounded_rectangles() -> Image.Image:
    # 背景の白(255)に極めて近い薄い塗り色 + 濃い輪郭線。大津の二値化1回
    # だけだと内部の薄い塗りが背景側に誤分類され、外側の輪郭線だけが
    # 前景として残ってしまう（穴埋めなしだと過分割の原因になる）
    img = Image.new("RGBA", (500, 200), (255, 255, 255, 255))
    draw = ImageDraw.Draw(img)
    pale_fill = (255, 250, 250, 255)
    draw.rounded_rectangle(
        (20, 20, 200, 170), radius=15, fill=pale_fill, outline=(0, 0, 0, 255), width=2
    )
    draw.rounded_rectangle(
        (300, 20, 480, 170), radius=15, fill=pale_fill, outline=(0, 0, 0, 255), width=2
    )
    return img


def test_two_separate_objects_split_into_two_regions() -> None:
    regions = split_regions(_two_separate_circles())

    assert len(regions) == 2


def test_regions_are_cropped_to_bounding_box() -> None:
    regions = split_regions(_two_separate_circles())

    for region in regions:
        # 元画像(300x150)よりずっと小さい、各円のバウンディングボックスに切り出されている
        assert region.size[0] < 300
        assert region.size[1] < 150


def test_regions_preserve_alpha_outside_shape_as_transparent() -> None:
    regions = split_regions(_two_separate_circles())

    for region in regions:
        rgba = region.convert("RGBA")
        corner_alpha = rgba.getpixel((0, 0))[3]
        assert corner_alpha == 0  # 円の外接矩形の四隅は円の外なので透明のまま


def test_single_object_returns_empty_list() -> None:
    regions = split_regions(_single_circle())

    assert regions == []


def test_fully_transparent_image_returns_empty_list() -> None:
    regions = split_regions(_fully_transparent())

    assert regions == []


def test_opaque_white_background_objects_split_via_otsu_fallback() -> None:
    # アルファチャンネルが実質すべて不透明な画像（PowerPoint上の通常の
    # 図形・写真をExportした場合）は、大津の二値化にフォールバックして
    # 分割できること
    regions = split_regions(_two_filled_circles_opaque_white_background())

    assert len(regions) == 2


def test_outline_only_shapes_split_via_contour_fill() -> None:
    # 塗りつぶしなし（線のみ）の図形は、内部にopeningで消えてしまう程度の
    # マス（線幅相当）しかないため、輪郭を塗りつぶしてから分割対象にする
    regions = split_regions(_two_outline_only_rounded_rectangles())

    assert len(regions) == 2


def test_outline_only_regions_are_opaque_inside_the_outline() -> None:
    # 輪郭を塗りつぶしたマスクをそのまま領域として使うため、線のみの図形も
    # 「輪郭の内側全体」が1つの物体として不透明に切り出される（線だけの
    # 輪として切り出すと、再配置時にPowerPoint上で違和感が出るため）
    regions = split_regions(_two_outline_only_rounded_rectangles())

    for region in regions:
        rgba = region.convert("RGBA")
        center = rgba.getpixel((rgba.width // 2, rgba.height // 2))
        assert center[3] == 255  # 図形の中心（輪郭の内側）も不透明
        corner = rgba.getpixel((0, 0))
        assert corner[3] == 0  # バウンディングボックスの外側四隅は透明のまま


def test_pale_filled_shapes_not_over_segmented_into_outline_and_interior() -> None:
    # 薄い塗り色（背景の白に極めて近い）の図形が、大津の二値化で内部を
    # 背景と誤分類され「輪郭線」と「内部」の2つの領域に過分割されないこと。
    # 2つの図形なので、期待される分割数はちょうど2（4にはならない）
    regions = split_regions(_two_pale_filled_rounded_rectangles())

    assert len(regions) == 2


def test_higher_distance_ratio_can_split_more_overlapping_objects() -> None:
    # 重なりの大きい2つの物体は、distance_ratioを上げないと1つの塊として
    # しか検出されない場合がある（ratio=0.5では未分割、0.8では分割される
    # ケースを固定して回帰させる）
    img = Image.new("RGBA", (300, 150), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((20, 20, 150, 130), fill=(255, 0, 0, 255))
    draw.ellipse((120, 20, 250, 130), fill=(0, 255, 0, 255))

    low_ratio_regions = split_regions(img, distance_ratio=0.5)
    high_ratio_regions = split_regions(img, distance_ratio=0.8)

    assert len(low_ratio_regions) <= len(high_ratio_regions)
    assert len(high_ratio_regions) == 2
