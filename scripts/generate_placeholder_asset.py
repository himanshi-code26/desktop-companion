"""
scripts/generate_placeholder_asset.py
======================================

Generates the placeholder pet sprite used until the real sprite-sheet
system (Phase 3) and artist-made pet packs exist. The image is drawn
procedurally with Pillow, so it carries no licensing baggage and can
be freely committed to a public, commercially-usable repository.

Run this any time you want to regenerate
``assets/sprites/placeholder_pet.png``:

    python scripts/generate_placeholder_asset.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


def generate_placeholder_pet(size: int = 128) -> Image.Image:
    """Draw a simple, friendly cat-like blob with a transparent background."""
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    body_color = (247, 168, 84, 255)
    outline_color = (120, 74, 24, 255)
    eye_color = (40, 30, 20, 255)
    nose_color = (200, 90, 90, 255)

    margin = size * 0.12

    # Tail (drawn first so the body overlaps it)
    tail_box = (size * 0.74, size * 0.52, size * 1.02, size * 0.84)
    draw.ellipse(tail_box, fill=body_color, outline=outline_color, width=3)

    # Body
    body_box = (margin, size * 0.30, size - margin, size - margin)
    draw.ellipse(body_box, fill=body_color, outline=outline_color, width=3)

    # Ears
    ear_w = size * 0.22
    ear_h = size * 0.24
    draw.polygon(
        [
            (size * 0.20, size * 0.34),
            (size * 0.20 + ear_w * 0.4, size * 0.34 - ear_h),
            (size * 0.20 + ear_w, size * 0.34),
        ],
        fill=body_color,
        outline=outline_color,
    )
    draw.polygon(
        [
            (size * 0.80 - ear_w, size * 0.34),
            (size * 0.80 - ear_w * 0.4, size * 0.34 - ear_h),
            (size * 0.80, size * 0.34),
        ],
        fill=body_color,
        outline=outline_color,
    )

    # Eyes
    eye_r = size * 0.045
    for cx, cy in ((size * 0.40, size * 0.52), (size * 0.60, size * 0.52)):
        draw.ellipse((cx - eye_r, cy - eye_r, cx + eye_r, cy + eye_r), fill=eye_color)

    # Nose
    nose_r = size * 0.03
    nx, ny = size * 0.5, size * 0.60
    draw.ellipse((nx - nose_r, ny - nose_r, nx + nose_r, ny + nose_r), fill=nose_color)

    # Whiskers
    for dy in (-6, 0, 6):
        draw.line(
            [(size * 0.10, size * 0.60 + dy), (size * 0.34, size * 0.60 + dy)],
            fill=outline_color,
            width=2,
        )
        draw.line(
            [(size * 0.66, size * 0.60 + dy), (size * 0.90, size * 0.60 + dy)],
            fill=outline_color,
            width=2,
        )

    return image


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    output_dir = project_root / "assets" / "sprites"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "placeholder_pet.png"

    image = generate_placeholder_pet()
    image.save(output_path)
    print(f"Wrote {output_path} ({image.size[0]}x{image.size[1]})")


if __name__ == "__main__":
    main()
