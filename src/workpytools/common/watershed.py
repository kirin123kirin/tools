from __future__ import annotations

import cv2
import numpy as np
from PIL import Image

_MORPH_KERNEL_SIZE = 3
_MORPH_OPEN_ITERATIONS = 2
_DILATE_ITERATIONS = 3
DEFAULT_DISTANCE_RATIO = 0.15
_OPAQUE_ALPHA_RATIO = 0.99  # これ以上の画素が不透明なら「アルファ情報なし」とみなす
_CORNER_SIZE_RATIO = 0.05  # 背景色サンプルに使う四隅の矩形サイズ（画像の短辺比）
DEFAULT_BACKGROUND_COLOR_DISTANCE = 20.0  # 背景サンプルとのRGBユークリッド距離がこれ以上なら前景
_MIN_CONTOUR_AREA = 16  # このピクセル面積未満の輪郭はノイズとして無視する


def split_regions(
    image: Image.Image,
    distance_ratio: float = DEFAULT_DISTANCE_RATIO,
    background_color_distance: float = DEFAULT_BACKGROUND_COLOR_DISTANCE,
) -> list[Image.Image]:
    """Split `image` into per-object transparent PNGs using marker-based
    watershed segmentation (distance transform, fully automatic -- no manual
    marker input required).

    The foreground mask is derived one of two ways, depending on whether the
    input already carries transparency:
    - If enough pixels are transparent, the alpha channel is trusted
      directly (transparent = background, opaque = foreground) -- this is
      the reliable case, typical of `touka`'s output.
    - Otherwise (an opaque image, e.g. a plain screenshot or an exported
      PowerPoint shape with a solid/white background), a single background
      color is estimated from the image's four corners (median RGB), and
      any pixel whose RGB Euclidean distance from that color exceeds
      `background_color_distance` is treated as foreground. This avoids
      Otsu's failure mode: Otsu splits the whole image into exactly two
      brightness classes, so a shape with a pale fill close to the
      background color (e.g. a light pink rectangle on white) can have its
      interior misclassified as background, leaving only the outline
      pixels as "foreground" -- which then get treated as a separate,
      hollow object from the interior, over-segmenting one shape into two.
      A fixed color-distance threshold from an explicit background sample
      has no such two-class constraint, so a shape's outline and its pale
      interior are both foreground consistently, as one contiguous blob.
      Outline-only shapes (no fill at all) would still vanish under the
      morphological opening below, since a thin outline alone has no
      interior mass to survive erosion -- so each outer contour found in
      the color-distance mask (RETR_CCOMP) is filled solid, holes
      included, before opening. As a side effect, a hollow shape's region
      is cropped out as fully opaque (interior included), not just the
      outline pixels -- treating "the shape" as the whole area it encloses
      reads more naturally once repositioned as its own picture shape.

    Follows the standard OpenCV watershed recipe: morphological opening to
    remove speckle noise, distance transform + threshold to seed one marker
    per touching object, then `cv2.watershed` to carve out the boundaries
    between them.

    `distance_ratio` (0-1) sets how large a peak in the distance transform
    must be, relative to the largest peak in the whole image, to seed its
    own marker. Lower values split more aggressively (risk of
    over-segmenting a single object); higher values require objects to be
    more clearly separated before they're split (risk of missing touching
    objects). The commonly cited OpenCV watershed tutorial value is 0.7
    (e.g. https://whitewell.sakura.ne.jp/OpenCV/Notebook/watershed.html),
    but in practice most PowerPoint shapes are cleanly separated already
    (unlike touching coins in the tutorial's example), so a much lower
    default (0.15) favors reliably splitting distinctly-separate objects
    over the tutorial's touching-object bias.

    `background_color_distance` sets how far (0-441.7, the max possible RGB
    Euclidean distance) a pixel's color must be from the estimated
    background color to count as foreground, for opaque images only.
    Higher values tolerate more background color variation (e.g. subtle
    gradients, JPEG noise) without misclassifying background as foreground,
    but risk missing objects whose color is close to the background.

    Each returned image is cropped to its region's bounding box, with pixels
    outside the region made transparent (alpha=0) and the region's original
    alpha (if any) preserved elsewhere. The crop origin (top-left corner of
    the bounding box, in source-image pixels) is available on the returned
    image as `.info["offset_x"]` / `.info["offset_y"]`, so callers can
    reposition each region relative to the original image. Returns an empty
    list if no more than one object is found (nothing to split).
    """
    rgba = np.array(image.convert("RGBA"))
    rgb = rgba[:, :, :3]
    alpha = rgba[:, :, 3]

    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

    foreground_mask = _foreground_mask(rgb, alpha, background_color_distance)

    kernel = np.ones((_MORPH_KERNEL_SIZE, _MORPH_KERNEL_SIZE), np.uint8)
    opened = cv2.morphologyEx(
        foreground_mask, cv2.MORPH_OPEN, kernel, iterations=_MORPH_OPEN_ITERATIONS
    )

    sure_background = cv2.dilate(opened, kernel, iterations=_DILATE_ITERATIONS)

    distance = cv2.distanceTransform(opened, cv2.DIST_L2, 5)
    max_distance = distance.max()
    if max_distance <= 0:
        return []

    _, sure_foreground = cv2.threshold(distance, distance_ratio * max_distance, 255, 0)
    sure_foreground = sure_foreground.astype(np.uint8)

    unknown = cv2.subtract(sure_background, sure_foreground)

    marker_count, markers = cv2.connectedComponents(sure_foreground)
    if marker_count <= 2:  # 背景(1) + 物体1個以下なら分割の余地がない
        return []

    markers = markers + 1
    markers[unknown == 255] = 0

    cv2.watershed(bgr, markers)

    regions: list[Image.Image] = []
    for label in range(2, marker_count + 1):
        region_mask = (markers == label).astype(np.uint8) * 255
        if not region_mask.any():
            continue
        regions.append(_crop_to_region(rgba, region_mask))

    return regions


def _foreground_mask(
    rgb: np.ndarray, alpha: np.ndarray, background_color_distance: float
) -> np.ndarray:
    """0/255 foreground mask, from alpha if present, otherwise background
    color-distance thresholding."""
    opaque_ratio = float(np.count_nonzero(alpha > 0)) / alpha.size
    if opaque_ratio < _OPAQUE_ALPHA_RATIO:
        return (alpha > 0).astype(np.uint8) * 255

    background_color = _estimate_background_color(rgb)
    diff = rgb.astype(np.float32) - background_color.astype(np.float32)
    distance = np.sqrt(np.sum(diff * diff, axis=2))
    mask = (distance > background_color_distance).astype(np.uint8) * 255

    return _fill_contours(mask)


def _estimate_background_color(rgb: np.ndarray) -> np.ndarray:
    """Median RGB color sampled from the image's four corners, used as the
    background reference for `_foreground_mask`."""
    height, width = rgb.shape[:2]
    corner_h = max(1, int(min(height, width) * _CORNER_SIZE_RATIO))
    corner_w = corner_h
    samples = np.concatenate(
        [
            rgb[:corner_h, :corner_w].reshape(-1, 3),
            rgb[:corner_h, -corner_w:].reshape(-1, 3),
            rgb[-corner_h:, :corner_w].reshape(-1, 3),
            rgb[-corner_h:, -corner_w:].reshape(-1, 3),
        ]
    )
    return np.asarray(np.median(samples, axis=0))


def _fill_contours(mask: np.ndarray) -> np.ndarray:
    """Fill each outer contour in a 0/255 mask solid, including any holes
    nested directly inside it.

    Covers a shape whose fill is entirely absent (a plain outline): the
    outline alone has no interior mass to survive the morphological opening
    that follows, so it would otherwise vanish from the mask entirely.
    RETR_CCOMP retrieves the outer contour and its immediate child contours
    (the holes) in one pass, so treating "outer contour, minus nothing" as
    one solid region turns a hollow outline into a blob the rest of the
    pipeline can work with.
    """
    contours, hierarchy = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    filled = np.zeros_like(mask)
    if hierarchy is None:
        return filled

    # hierarchy[0][i] = (next, previous, first_child, parent); parent == -1 は最外周輪郭
    for i, contour in enumerate(contours):
        is_outer = hierarchy[0][i][3] == -1
        if not is_outer or cv2.contourArea(contour) < _MIN_CONTOUR_AREA:
            continue
        cv2.drawContours(filled, [contour], -1, (255,), thickness=cv2.FILLED)
    return filled


def _crop_to_region(rgba: np.ndarray, region_mask: np.ndarray) -> Image.Image:
    """Crop `rgba` to `region_mask`'s bounding box, zeroing alpha outside the mask.

    The crop origin is stashed in the result's `.info` dict as
    "offset_x"/"offset_y" (source-image pixel coordinates).
    """
    ys, xs = np.nonzero(region_mask)
    y0, y1 = ys.min(), ys.max() + 1
    x0, x1 = xs.min(), xs.max() + 1

    cropped = rgba[y0:y1, x0:x1].copy()
    cropped_mask = region_mask[y0:y1, x0:x1]
    cropped[:, :, 3] = np.minimum(cropped[:, :, 3], cropped_mask)

    result = Image.fromarray(cropped, mode="RGBA")
    result.info["offset_x"] = int(x0)
    result.info["offset_y"] = int(y0)
    return result
