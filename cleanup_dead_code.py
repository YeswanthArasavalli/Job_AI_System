#!/usr/bin/env python3
"""
cleanup_dead_code.py

Removes confirmed dead pipeline modules and report clutter from the system.
Run from the job_ai_system/ directory.

WHAT THIS REMOVES:
  Pipeline dead code (2,674 LOC, 0 functionality lost):
    - optimization_engine.py  (590 lines — superseded by core.py inline logic)
    - precision_engine.py     (872 lines — never imported from main flow)
    - reality_validation.py   (782 lines — never imported from main flow)
    - career_intelligence.py  (430 lines — superseded by hiring_simulation.py)

  Development artifact reports (root dir clutter):
    - shortlist_engine_report* (9 files)
    - hardening_report* (3 files)
    - execution_engine_report* (3 files)
    - final_validation_report* (3 files)
    - output_quality_hardening_report* (5 files)

  Stale test files (test files with no corresponding module):
    - [listed below — manual review recommended]

WHAT THIS PRESERVES:
  - All modules currently imported in the main execution path
  - All test files in tests/ directory
  - All data files
  - All configuration

HOW TO USE:
  python cleanup_dead_code.py --dry-run    # show what would be removed
  python cleanup_dead_code.py              # actually remove it
"""

import argparse
import os
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).parent

# ================================================================
# FILES TO REMOVE
# ================================================================

DEAD_PIPELINE_MODULES = [
    "pipeline/optimization_engine.py",
    "pipeline/precision_engine.py",
    "pipeline/reality_validation.py",
    "pipeline/career_intelligence.py",
]

REPORT_CLUTTER = [
    "shortlist_engine_report5",
    "shortlist_engine_report6",
    "shortlist_engine_report7",
    "shortlist_engine_report8",
    "shortlist_engine_report_1",
    "shortlist_engine_report_2",
    "shortlist_engine_report_3",
    "shortlist_engine_report_4",
    "hardening_report_1",
    "hardening_report_2",
    "execution_engine_report1",
    "execution_engine_report_1",
    "execution_engine_report_2",
    "final_validation_report_1",
    "final_validation_report_2",
    "output_quality_hardening_report_1",
    "output_quality_hardening_report_2",
    "output_quality_hardening_report_3",
    "output_quality_hardening_report_4",
    "execution_hardening_plan 1",  # duplicate of .md version
]

# Stale test files (tests for modules that no longer exist or have been
# superseded — review before removing)
STALE_TEST_FILES_REVIEW = [
    # These test dead modules — safe to remove after verifying
    "test_adaptive.py",     # tests pipeline/adaptive_engine.py (still exists but unused)
    "test_agent.py",        # tests career_agent (standalone, not in main pipeline)
    "test_monitor.py",      # tests job_monitor (standalone, not in main pipeline)
    # These duplicate newer test coverage:
    "test_stability.py",    # overlaps with tests/determinism_proof.py
]


# ================================================================
# RENAME REFACTORED FILES TO PRODUCTION
# ================================================================

FILES_TO_PROMOTE = [
    # (source, target) — rename new refactored files to replace originals
    ("pipeline/core_refactored.py", "pipeline/core.py"),
    ("database/db_manager_v2.py", "database/db_manager.py"),
]


def remove_file(path: Path, dry_run: bool) -> None:
    if not path.exists():
        print(f"  [skip] not found: {path}")
        return
    size = path.stat().st_size
    if dry_run:
        print(f"  [would remove] {path} ({size:,} bytes)")
    else:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        print(f"  [removed] {path} ({size:,} bytes)")


def promote_file(source: Path, target: Path, dry_run: bool) -> None:
    if not source.exists():
        print(f"  [skip] source not found: {source}")
        return
    if dry_run:
        print(f"  [would promote] {source} → {target}")
    else:
        # Backup original
        if target.exists():
            backup = target.with_suffix(target.suffix + ".bak")
            shutil.copy2(target, backup)
            print(f"  [backed up] {target} → {backup}")
        shutil.copy2(source, target)
        source.unlink()
        print(f"  [promoted] {source} → {target}")


def main():
    parser = argparse.ArgumentParser(description="Remove dead code from job_ai_system")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be removed without removing")
    parser.add_argument("--promote", action="store_true", help="Also promote refactored files to replace originals")
    args = parser.parse_args()

    mode = "DRY RUN" if args.dry_run else "LIVE"
    print(f"\n=== Dead Code Cleanup [{mode}] ===\n")

    # 1. Dead pipeline modules
    print("1. Dead pipeline modules:")
    total_bytes = 0
    for rel_path in DEAD_PIPELINE_MODULES:
        path = BASE_DIR / rel_path
        if path.exists():
            total_bytes += path.stat().st_size
        remove_file(path, args.dry_run)

        # Also remove pycache
        pycache = BASE_DIR / rel_path.replace(".py", ".cpython-314.pyc").replace(
            rel_path.split("/")[0], rel_path.split("/")[0] + "/__pycache__"
        )
        if pycache.exists():
            remove_file(pycache, args.dry_run)

    print(f"\n  Total dead module bytes: {total_bytes:,}")

    # 2. Report clutter
    print("\n2. Report clutter (root dir):")
    for rel_path in REPORT_CLUTTER:
        remove_file(BASE_DIR / rel_path, args.dry_run)

    # 3. Stale test files (advisory)
    print("\n3. Stale test files [ADVISORY — review before removing]:")
    for rel_path in STALE_TEST_FILES_REVIEW:
        path = BASE_DIR / rel_path
        if path.exists():
            print(f"  [review] {path} ({path.stat().st_size:,} bytes) — verify before removing")
        else:
            print(f"  [skip] not found: {path}")

    # 4. Promote refactored files (optional)
    if args.promote:
        print("\n4. Promoting refactored files:")
        for source_rel, target_rel in FILES_TO_PROMOTE:
            promote_file(BASE_DIR / source_rel, BASE_DIR / target_rel, args.dry_run)
    else:
        print("\n4. Refactored files [NOT promoted — run with --promote to replace originals]:")
        for source_rel, target_rel in FILES_TO_PROMOTE:
            source = BASE_DIR / source_rel
            if source.exists():
                print(f"  [ready] {source_rel} → {target_rel}")

    print("\n=== Done ===")
    if args.dry_run:
        print("Run without --dry-run to apply changes.")


if __name__ == "__main__":
    main()
