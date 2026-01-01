#!/usr/bin/env python3
"""Migration script to rename SLO files to annotations format.

This script:
1. Renames slo/ directory to annotations/ (if slo/ exists)
2. Renames *_slo.json files to *_annotations.json
3. Optionally updates the 'format' field in JSON files

Usage:
    python scripts/migrate_slo_to_annotations.py [--dry-run] [--update-format]

Options:
    --dry-run       Show what would be done without making changes
    --update-format Update the 'format' field in JSON files to 'annotations-v1' or 'annotations-v2'
"""

import argparse
import json
import shutil
from pathlib import Path


def migrate_directory(project_root: Path, dry_run: bool = False) -> bool:
    """Rename slo/ to annotations/ if it exists."""
    slo_dir = project_root / "slo"
    annotations_dir = project_root / "annotations"

    if not slo_dir.exists():
        print(f"  No slo/ directory found at {slo_dir}")
        return False

    if annotations_dir.exists():
        print(f"  annotations/ directory already exists at {annotations_dir}")
        print(f"  Merging contents from slo/ to annotations/")
        if not dry_run:
            # Move files from slo/ to annotations/
            for f in slo_dir.iterdir():
                dest = annotations_dir / f.name
                if dest.exists():
                    print(f"    Skipping {f.name} (already exists)")
                else:
                    print(f"    Moving {f.name}")
                    shutil.move(str(f), str(dest))
            # Remove empty slo/ directory
            try:
                slo_dir.rmdir()
                print(f"  Removed empty slo/ directory")
            except OSError:
                print(f"  Warning: slo/ directory not empty after merge")
        return True

    print(f"  Renaming {slo_dir} -> {annotations_dir}")
    if not dry_run:
        slo_dir.rename(annotations_dir)
    return True


def migrate_files(annotations_dir: Path, dry_run: bool = False, update_format: bool = False) -> int:
    """Rename *_slo.json files to *_annotations.json."""
    if not annotations_dir.exists():
        print(f"  No annotations/ directory found")
        return 0

    count = 0
    for slo_file in annotations_dir.glob("*_slo.json"):
        new_name = slo_file.name.replace("_slo.json", "_annotations.json")
        new_path = slo_file.parent / new_name

        print(f"  Renaming {slo_file.name} -> {new_name}")

        if not dry_run:
            # Read, optionally update format, and write to new location
            if update_format:
                with open(slo_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Update format field
                version = data.get('version', 1)
                if version == 2:
                    data['format'] = 'annotations-v2'
                else:
                    data['format'] = 'annotations-v1'

                with open(new_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)

                # Remove old file
                slo_file.unlink()
            else:
                slo_file.rename(new_path)

        count += 1

    return count


def main():
    parser = argparse.ArgumentParser(
        description="Migrate SLO files to annotations format"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    parser.add_argument(
        "--update-format",
        action="store_true",
        help="Update the 'format' field in JSON files"
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).parent.parent,
        help="Project root directory (default: parent of scripts/)"
    )

    args = parser.parse_args()

    print(f"SLO to Annotations Migration")
    print(f"{'=' * 40}")
    print(f"Project root: {args.project_root}")
    print(f"Dry run: {args.dry_run}")
    print(f"Update format field: {args.update_format}")
    print()

    # Step 1: Migrate directory
    print("Step 1: Directory migration")
    migrate_directory(args.project_root, args.dry_run)
    print()

    # Step 2: Migrate files
    print("Step 2: File renaming")
    annotations_dir = args.project_root / "annotations"
    count = migrate_files(annotations_dir, args.dry_run, args.update_format)
    print()

    # Summary
    print("Summary")
    print("-" * 40)
    if count > 0:
        print(f"  Migrated {count} file(s)")
    else:
        print("  No files needed migration")

    if args.dry_run:
        print("\n  (Dry run - no changes made)")


if __name__ == "__main__":
    main()
