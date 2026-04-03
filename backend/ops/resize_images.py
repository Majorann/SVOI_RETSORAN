from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageOps


SUPPORTED_EXTENSIONS = {".webp", ".png", ".jpg", ".jpeg"}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Crop images to a square and resize them in place."
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=str(Path(__file__).resolve().parents[1] / "static" / "menu_items"),
        help="Folder with images. Default: backend/static/menu_items",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=480,
        help="Target square size in pixels. Default: 480",
    )
    parser.add_argument(
        "--quality",
        type=int,
        default=82,
        help="Quality for JPG/WEBP. Default: 82",
    )
    return parser.parse_args()


def iter_images(target_dir: Path):
    for path in sorted(target_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        yield path


def save_image(image: Image.Image, path: Path, quality: int):
    suffix = path.suffix.lower()
    save_kwargs = {}

    if suffix in {".jpg", ".jpeg"}:
        if image.mode not in {"RGB", "L"}:
            image = image.convert("RGB")
        save_kwargs.update({"quality": quality, "optimize": True, "progressive": True})
    elif suffix == ".png":
        save_kwargs.update({"optimize": True})
    elif suffix == ".webp":
        save_kwargs.update({"quality": quality, "method": 6})

    image.save(path, **save_kwargs)


def resize_one(path: Path, size: int, quality: int):
    before_bytes = path.stat().st_size
    with Image.open(path) as original:
        fitted = ImageOps.fit(
            original,
            (size, size),
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )
        save_image(fitted, path, quality)
    after_bytes = path.stat().st_size
    return before_bytes, after_bytes


def main():
    args = parse_args()
    target_dir = Path(args.target).resolve()
    if not target_dir.exists():
        raise SystemExit(f"Folder not found: {target_dir}")
    if not target_dir.is_dir():
        raise SystemExit(f"Target is not a folder: {target_dir}")
    if args.size <= 0:
        raise SystemExit("--size must be greater than 0")
    if not 1 <= args.quality <= 100:
        raise SystemExit("--quality must be between 1 and 100")

    processed = 0
    total_before = 0
    total_after = 0

    for image_path in iter_images(target_dir):
        before_bytes, after_bytes = resize_one(image_path, args.size, args.quality)
        processed += 1
        total_before += before_bytes
        total_after += after_bytes
        print(
            "[ok] {0} | {1:.1f} KB -> {2:.1f} KB".format(
                image_path,
                before_bytes / 1024,
                after_bytes / 1024,
            )
        )

    if processed == 0:
        print(f"No images found in {target_dir}")
        return

    saved_kb = (total_before - total_after) / 1024
    print(
        "\nDone. Processed {0} image(s). Total: {1:.1f} KB -> {2:.1f} KB, saved {3:.1f} KB.".format(
            processed,
            total_before / 1024,
            total_after / 1024,
            saved_kb,
        )
    )


if __name__ == "__main__":
    main()
