"""
scripts/remove_checkerboard_background.py
============================================

Some AI image generators export a "transparent" sticker by literally
drawing the checkerboard pattern that editors use to *represent*
transparency, instead of an actual alpha channel. The result looks
transparent in a preview but is 100% opaque pixels when you inspect
it — which is exactly what would show up as a gray-and-white box
behind the pet in the desktop app.

This script detects that checkerboard pattern and converts it to real
transparency:

1. Identify the checkerboard's two near-gray tile colors by sampling
   the image border (which is guaranteed to be background).
2. Flood-fill from the border, following only checkerboard-colored
   pixels, to find the connected background region. This is important:
   a plain color-threshold would also wipe out gray pixels *inside*
   the character (e.g. this sticker's gray pants and sneakers), since
   flood fill only removes pixels that are both checker-colored *and*
   reachable from the border without crossing through non-checker
   pixels.
3. Feather a couple of pixels at the boundary so the cutout doesn't
   leave a harsh, aliased edge against the character's outline.

Usage:
    python scripts/remove_checkerboard_background.py <input.png> <output.png>
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import binary_dilation, distance_transform_edt
from scipy.ndimage import label as connected_components


def _sample_border_tile_colors(rgb: np.ndarray, border_width: int = 12) -> list[np.ndarray]:
    """Return the distinct near-gray tile colors found along the image border."""
    h, w, _ = rgb.shape
    border_pixels = np.concatenate(
        [
            rgb[:border_width, :, :].reshape(-1, 3),
            rgb[-border_width:, :, :].reshape(-1, 3),
            rgb[:, :border_width, :].reshape(-1, 3),
            rgb[:, -border_width:, :].reshape(-1, 3),
        ]
    )
    # Keep only near-gray pixels (checkerboard tiles are grayscale; the
    # character's skin/hair/clothing colors are not).
    channel_spread = border_pixels.max(axis=1).astype(int) - border_pixels.min(axis=1).astype(int)
    grayish = border_pixels[channel_spread <= 6]

    if grayish.size == 0:
        raise ValueError("Could not find any near-gray border pixels to sample.")

    brightness = grayish.mean(axis=1)
    dark_tile = grayish[brightness < np.median(brightness)].mean(axis=0)
    light_tile = grayish[brightness >= np.median(brightness)].mean(axis=0)
    return [dark_tile, light_tile]


def _is_checker_colored(
    rgb: np.ndarray, tile_colors: list[np.ndarray], tolerance: float = 18.0
) -> np.ndarray:
    """Boolean mask of pixels close to either checkerboard tile color."""
    mask = np.zeros(rgb.shape[:2], dtype=bool)
    for tile_color in tile_colors:
        distance = np.linalg.norm(rgb.astype(float) - tile_color, axis=2)
        mask |= distance <= tolerance
    return mask


def _border_connected_mask(candidate_mask: np.ndarray) -> np.ndarray:
    """Keep only the True regions of candidate_mask that touch the image border."""
    labeled, _ = connected_components(candidate_mask)
    border = set(labeled[0, :]) | set(labeled[-1, :]) | set(labeled[:, 0]) | set(labeled[:, -1])
    border_labels = border
    border_labels.discard(0)
    return np.isin(labeled, list(border_labels))


def remove_checkerboard_background(input_path: Path, output_path: Path) -> None:
    image = Image.open(input_path).convert("RGBA")
    array = np.array(image)
    rgb = array[:, :, :3]

    tile_colors = _sample_border_tile_colors(rgb)
    checker_candidates = _is_checker_colored(rgb, tile_colors)
    background_mask = _border_connected_mask(checker_candidates)

    # Feather the cutout edge: pixels just outside the removed region
    # get partial alpha instead of a hard 0/255 cliff, avoiding a harsh
    # aliased ring around the character.
    feather_px = 2
    dilated = binary_dilation(background_mask, iterations=feather_px)
    edge_band = dilated & ~background_mask
    distance_into_band = distance_transform_edt(~background_mask) * edge_band
    max_distance = distance_into_band.max() or 1.0
    feather_alpha = np.clip(distance_into_band / max_distance, 0.0, 1.0)

    alpha = array[:, :, 3].astype(float)
    alpha[background_mask] = 0.0
    alpha[edge_band] = alpha[edge_band] * feather_alpha[edge_band]

    array[:, :, 3] = alpha.astype(np.uint8)
    Image.fromarray(array, mode="RGBA").save(output_path)

    removed_fraction = background_mask.mean()
    print(
        f"Wrote {output_path} — removed {removed_fraction:.1%} of pixels as "
        f"background (checkerboard tile colors: "
        f"{tuple(tile_colors[0].round().astype(int))}, "
        f"{tuple(tile_colors[1].round().astype(int))})"
    )


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python scripts/remove_checkerboard_background.py <input.png> <output.png>")
        sys.exit(1)
    remove_checkerboard_background(Path(sys.argv[1]), Path(sys.argv[2]))


if __name__ == "__main__":
    main()
