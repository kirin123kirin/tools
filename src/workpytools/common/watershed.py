from __future__ import annotations

import cv2
import numpy as np
from PIL import Image

_MORPH_KERNEL_SIZE = 3
_MORPH_OPEN_ITERATIONS = 2
_DILATE_ITERATIONS = 3
DEFAULT_DISTANCE_RATIO = 0.7


def split_regions(
    image: Image.Image, distance_ratio: float = DEFAULT_DISTANCE_RATIO
) -> list[Image.Image]:
    """Split `image` into per-object transparent PNGs using marker-based
    watershed segmentation (distance transform, fully automatic -- no manual
    marker input required).

    The foreground mask comes straight from the alpha channel (transparent =
    background, opaque = foreground). This assumes the input has already
    had its background removed (e.g. `touka`'s output) -- for an opaque
    photo, alpha is uniformly 255 and the whole image is treated as one
    connected foreground blob, which `cv2.watershed` then splits using the
    distance-transform markers below.

    Follows the standard OpenCV watershed recipe: morphological opening to
    remove speckle noise, distance transform + threshold to seed one marker
    per touching object, then `cv2.watershed` to carve out the boundaries
    between them.

    `distance_ratio` (0-1) sets how large a peak in the distance transform
    must be, relative to the largest peak in the whole image, to seed its
    own marker. Lower values split more aggressively (risk of
    over-segmenting a single object); higher values require objects to be
    more clearly separated before they're split (risk of missing touching
    objects). 0.7 follows the commonly cited OpenCV watershed tutorial
    value (e.g. https://whitewell.sakura.ne.jp/OpenCV/Notebook/watershed.html),
    which favors confidently separating touching objects over aggressive
    splitting.

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

    foreground_mask = (alpha > 0).astype(np.uint8) * 255

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
