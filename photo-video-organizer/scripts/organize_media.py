#!/usr/bin/env python3
"""Organize photos/videos by timestamp and optionally rename them by date."""

from __future__ import annotations

import argparse
import filecmp
import os
import shutil
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


DEFAULT_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".heic",
    ".heif",
    ".tif",
    ".tiff",
    ".webp",
    ".gif",
    ".bmp",
    ".mp4",
    ".mov",
    ".m4v",
    ".avi",
    ".3gp",
    ".mts",
    ".mkv",
}


@dataclass
class MediaFile:
    path: Path
    timestamp: float

    @property
    def date(self) -> datetime:
        return datetime.fromtimestamp(self.timestamp)


def media_timestamp(path: Path) -> float:
    stat = path.stat()
    return getattr(stat, "st_birthtime", None) or stat.st_mtime


def is_media(path: Path, extensions: set[str]) -> bool:
    return path.is_file() and not path.name.startswith("._") and path.suffix.lower() in extensions


def scan_media(root: Path, extensions: set[str]) -> list[MediaFile]:
    items: list[MediaFile] = []
    for dirpath, _, filenames in os.walk(root):
        directory = Path(dirpath)
        for filename in filenames:
            path = directory / filename
            if is_media(path, extensions):
                items.append(MediaFile(path=path, timestamp=media_timestamp(path)))
    items.sort(key=lambda item: (str(item.path.parent).lower(), item.timestamp, item.path.name.lower()))
    return items


def target_directory(root: Path, item: MediaFile, year_prefix: str, month_suffix: str) -> Path:
    dt = item.date
    return root / f"{year_prefix}{dt.year}" / f"{dt.month}{month_suffix}"


def sidecar_for(path: Path) -> Path:
    return path.with_name(f"._{path.name}")


def next_available(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    index = 1
    while True:
        candidate = path.with_name(f"{stem}-{index}{suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def archive_media(
    root: Path,
    items: list[MediaFile],
    *,
    year_prefix: str,
    month_suffix: str,
    include_sidecars: bool,
    dedupe_identical: bool,
    dry_run: bool,
) -> dict[str, int]:
    stats = {
        "total_media": len(items),
        "already_correct": 0,
        "moved": 0,
        "renamed_for_collision": 0,
        "deduped_identical": 0,
        "moved_sidecars": 0,
        "errors": 0,
    }

    for item in items:
        if not item.path.exists():
            continue
        dest_dir = target_directory(root, item, year_prefix, month_suffix)
        if item.path.parent == dest_dir:
            stats["already_correct"] += 1
            continue

        dest = dest_dir / item.path.name
        final_name = item.path.name

        if dest.exists():
            same_size = item.path.stat().st_size == dest.stat().st_size
            same_bytes = same_size and filecmp.cmp(item.path, dest, shallow=False)
            if same_bytes and dedupe_identical:
                print(f"DEDUP {item.path} -> existing {dest}")
                old_sidecar = sidecar_for(item.path)
                new_sidecar = sidecar_for(dest)
                if include_sidecars and old_sidecar.exists() and not new_sidecar.exists():
                    if not dry_run:
                        dest_dir.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(old_sidecar), str(new_sidecar))
                    stats["moved_sidecars"] += 1
                if not dry_run:
                    item.path.unlink()
                    if include_sidecars and old_sidecar.exists():
                        old_sidecar.unlink()
                stats["deduped_identical"] += 1
                continue
            dest = next_available(dest)
            final_name = dest.name
            stats["renamed_for_collision"] += 1

        print(f"MOVE {item.path} -> {dest}")
        if not dry_run:
            try:
                dest_dir.mkdir(parents=True, exist_ok=True)
                shutil.move(str(item.path), str(dest))
                old_sidecar = sidecar_for(item.path)
                if include_sidecars and old_sidecar.exists():
                    new_sidecar = dest_dir / f"._{final_name}"
                    new_sidecar = next_available(new_sidecar)
                    shutil.move(str(old_sidecar), str(new_sidecar))
                    stats["moved_sidecars"] += 1
            except OSError as exc:
                print(f"ERROR moving {item.path}: {exc}", file=sys.stderr)
                stats["errors"] += 1
                continue
        stats["moved"] += 1

    return stats


def date_name(item: MediaFile) -> str:
    return item.date.strftime("%Y%m%d")


def plan_renames(items: list[MediaFile]) -> list[tuple[Path, Path]]:
    planned: list[tuple[Path, Path]] = []
    used: set[Path] = set()

    for item in sorted(items, key=lambda x: (str(x.path.parent).lower(), date_name(x), x.path.suffix.lower(), x.path.name.lower())):
        if not item.path.exists():
            continue
        directory = item.path.parent
        suffix = item.path.suffix
        base = date_name(item)
        index = 0
        while True:
            if index == 0:
                target = directory / f"{base}{suffix}"
            else:
                target = directory / f"{base}-{index:03d}{suffix}"
            key = Path(str(target).lower())
            if key not in used and (not target.exists() or target == item.path):
                used.add(key)
                break
            index += 1
        if target != item.path:
            planned.append((item.path, target))

    return planned


def rename_media(items: list[MediaFile], *, include_sidecars: bool, dry_run: bool) -> dict[str, int]:
    plan = plan_renames(items)
    stats = {
        "planned_renames": len(plan),
        "renamed": 0,
        "renamed_sidecars": 0,
        "errors": 0,
    }

    for src, dest in plan[:50]:
        print(f"RENAME {src} -> {dest}")
    if len(plan) > 50:
        print(f"... {len(plan) - 50} more renames")
    if dry_run:
        return stats

    token = uuid.uuid4().hex
    staged: list[tuple[Path, Path, Path]] = []
    for index, (src, dest) in enumerate(plan):
        if not src.exists():
            continue
        tmp = src.with_name(f".rename-tmp-{token}-{index:06d}{src.suffix}")
        try:
            shutil.move(str(src), str(tmp))
            staged.append((tmp, src, dest))
        except OSError as exc:
            print(f"ERROR staging {src}: {exc}", file=sys.stderr)
            stats["errors"] += 1

    for tmp, original, dest in staged:
        try:
            shutil.move(str(tmp), str(dest))
            stats["renamed"] += 1
            if include_sidecars:
                old_sidecar = original.with_name(f"._{original.name}")
                new_sidecar = dest.with_name(f"._{dest.name}")
                if old_sidecar.exists() and old_sidecar != new_sidecar:
                    if new_sidecar.exists():
                        old_sidecar.unlink()
                    else:
                        shutil.move(str(old_sidecar), str(new_sidecar))
                        stats["renamed_sidecars"] += 1
        except OSError as exc:
            print(f"ERROR renaming {original}: {exc}", file=sys.stderr)
            stats["errors"] += 1
            if tmp.exists() and not original.exists():
                shutil.move(str(tmp), str(original))

    return stats


def print_stats(title: str, stats: dict[str, int]) -> None:
    print(title)
    for key, value in stats.items():
        print(f"{key}={value}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Organize photos/videos by timestamp.")
    parser.add_argument("--root", required=True, type=Path, help="Media library root directory.")
    parser.add_argument("--archive", action="store_true", help="Move media into year/month folders.")
    parser.add_argument("--rename", action="store_true", help="Rename media in place to YYYYMMDD.ext.")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without modifying files.")
    parser.add_argument("--dedupe-identical", action="store_true", help="Delete source only when destination has identical bytes.")
    parser.add_argument("--include-sidecars", action="store_true", help="Move/rename macOS ._ sidecar files with media.")
    parser.add_argument("--year-prefix", default="_", help='Year folder prefix, default "_".')
    parser.add_argument("--month-suffix", default="月", help='Month folder suffix, default "月".')
    parser.add_argument(
        "--extensions",
        default=",".join(sorted(ext.lstrip(".") for ext in DEFAULT_EXTENSIONS)),
        help="Comma-separated extensions to include.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.expanduser().resolve()
    if not root.is_dir():
        print(f"Root is not a directory: {root}", file=sys.stderr)
        return 2
    if not args.archive and not args.rename:
        print("Choose at least one operation: --archive and/or --rename", file=sys.stderr)
        return 2

    extensions = {ext.strip().lower() for ext in args.extensions.split(",") if ext.strip()}
    extensions = {ext if ext.startswith(".") else f".{ext}" for ext in extensions}

    items = scan_media(root, extensions)
    print(f"scanned_media={len(items)}")

    if args.archive:
        archive_stats = archive_media(
            root,
            items,
            year_prefix=args.year_prefix,
            month_suffix=args.month_suffix,
            include_sidecars=args.include_sidecars,
            dedupe_identical=args.dedupe_identical,
            dry_run=args.dry_run,
        )
        print_stats("archive_summary", archive_stats)

    if args.rename:
        if args.archive and not args.dry_run:
            items = scan_media(root, extensions)
        rename_stats = rename_media(items, include_sidecars=args.include_sidecars, dry_run=args.dry_run)
        print_stats("rename_summary", rename_stats)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
