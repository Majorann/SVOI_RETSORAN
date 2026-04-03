from __future__ import annotations

import argparse
import os
from pathlib import Path


def normalize_component(name: str) -> str:
    text = str(name or "").strip().strip("/\\")
    if not text:
        return ""
    try:
        text.encode("utf-8")
        return text
    except UnicodeEncodeError:
        raw_bytes = os.fsencode(text)
        for encoding in ("utf-8", "cp1251", "latin-1"):
            try:
                decoded = raw_bytes.decode(encoding)
                decoded.encode("utf-8")
                return decoded
            except (UnicodeDecodeError, UnicodeEncodeError):
                continue
        return raw_bytes.decode("utf-8", errors="ignore")


def iter_entries(root: Path):
    for current_root, dir_names, file_names in os.walk(root, topdown=False):
        current_path = Path(current_root)
        for filename in file_names:
            yield current_path / filename
        for dirname in dir_names:
            yield current_path / dirname


def rename_entry(path: Path, dry_run: bool) -> bool:
    normalized_name = normalize_component(path.name)
    if not normalized_name or normalized_name == path.name:
        return False

    target = path.with_name(normalized_name)
    if target.exists():
        print(f"[skip] target exists: {target}")
        return False

    print(f"[rename] {path} -> {target}")
    if not dry_run:
        path.rename(target)
    return True


def main():
    parser = argparse.ArgumentParser(description="Repair static filenames with broken encoding.")
    parser.add_argument(
        "targets",
        nargs="*",
        default=[
            str(Path(__file__).resolve().parents[1] / "static" / "menu_items"),
            str(Path(__file__).resolve().parents[1] / "static" / "promo_items"),
        ],
        help="Directories to scan. Defaults to backend/static/menu_items and backend/static/promo_items.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Only print planned renames.")
    args = parser.parse_args()

    renamed = 0
    for raw_target in args.targets:
        target = Path(raw_target).resolve()
        if not target.exists():
            print(f"[skip] missing: {target}")
            continue
        for entry in iter_entries(target):
            if rename_entry(entry, args.dry_run):
                renamed += 1

    print(f"Done. Renamed {renamed} entr{'y' if renamed == 1 else 'ies'}.")


if __name__ == "__main__":
    main()
