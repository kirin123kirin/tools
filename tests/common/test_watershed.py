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
