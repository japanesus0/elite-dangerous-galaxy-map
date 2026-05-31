#!/usr/bin/env python3
"""
Elite Dangerous Journal Log Watcher
=====================================
Long-running service that polls JournalLogs/ for new Journal*.log files,
loads them into PostgreSQL, then moves them to JournalLogs/Loaded/.

Only files that have NOT been recorded in `processed_logs` are loaded —
duplicate-safe even if a file is dropped twice (ON CONFLICT DO NOTHING
handles row-level dedup; processed_logs prevents re-processing entirely).

Usage (via docker compose):
    docker compose up -d elite-watcher

Environment variables:
    ED_LOGS_DIR      Directory to watch  (default: /data/logs)
    POLL_INTERVAL    Seconds between polls (default: 30)
    POSTGRES_HOST / PORT / DB / USER / PASSWORD  (same as ETL)
"""

import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import psycopg2

# Import shared logic from etl.py (same /app directory in the container)
from etl import (
    connect,
    ensure_jump_aggregates,
    ensure_processed_logs_table,
    get_processed_files,
    mark_files_processed,
    process_files_list,
)

LOGS_DIR      = Path(os.environ.get("ED_LOGS_DIR", "/data/logs"))
LOADED_DIR    = LOGS_DIR / "Loaded"
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "30"))


# ── helpers ────────────────────────────────────────────────────

def find_new_files(con) -> list:
    """Return Journal*.log files in the root watch dir not yet processed."""
    # Only top-level files — Loaded/ subdirectory is intentionally excluded
    candidates = sorted(LOGS_DIR.glob("Journal*.log"))
    processed  = get_processed_files(con)
    return [f for f in candidates if f.name not in processed]


def move_already_processed(con) -> None:
    """Startup cleanup: move files that the ETL already loaded but never moved.

    The ETL records every file it processes in `processed_logs` but does NOT
    move files to Loaded/ — that's the watcher's job.  On first start after
    an ETL run this function finds every Journal*.log still sitting in the
    root directory that is already recorded as processed, and moves it across
    so the directory stays clean going forward.
    """
    LOADED_DIR.mkdir(exist_ok=True)
    candidates = sorted(LOGS_DIR.glob("Journal*.log"))
    if not candidates:
        return

    processed = get_processed_files(con)
    to_move   = [f for f in candidates if f.name in processed]
    if not to_move:
        return

    print(f"Startup cleanup: moving {len(to_move)} already-processed file(s) to Loaded/ …",
          flush=True)
    for fpath in to_move:
        dest = LOADED_DIR / fpath.name
        if dest.exists():
            dest = LOADED_DIR / f"{fpath.stem}_dup_{int(time.time())}{fpath.suffix}"
        try:
            shutil.move(str(fpath), str(dest))
        except Exception as e:
            print(f"  ✗ could not move {fpath.name}: {e}", file=sys.stderr)
    print(f"Startup cleanup complete — {len(to_move)} file(s) moved.\n", flush=True)


def _move_to_loaded(fpath: Path) -> None:
    """Move a processed journal file into the Loaded/ subdirectory.

    Filesystem-only — assumes the file is already recorded in processed_logs.
    If a same-named file already exists in Loaded/ (e.g. a re-drop), the new
    one is suffixed with a unix timestamp to avoid clobbering.
    """
    fname = fpath.name
    dest  = LOADED_DIR / fname
    if dest.exists():
        dest = LOADED_DIR / f"{fpath.stem}_dup_{int(time.time())}{fpath.suffix}"
    try:
        shutil.move(str(fpath), str(dest))
    except Exception as e:
        # File processed but couldn't be moved — log and keep going. The
        # next poll will skip it (it's already in processed_logs) but it'll
        # clutter the watch dir until the user resolves the FS issue.
        print(f"  ✗ could not move {fname}: {e}", file=sys.stderr)


def load_batch(new_files: list, con) -> None:
    """Parse + insert + refresh once for the whole batch, then move files.

    This is the watcher's hot path. Calling process_files_list with the
    entire batch coalesces what would otherwise be N individual
    REFRESH MATERIALIZED VIEW calls (one per file, ~3-4 s each at current
    data volume) into a single refresh — dramatically faster on backlogs.

    Per-file parse errors are caught inside process_files_list, so one bad
    file doesn't kill the batch. A whole-batch DB failure raises out of
    this function with no files marked processed — they'll be retried on
    the next poll cycle.
    """
    if not new_files:
        return

    # process_files_list logs per-file in verbose mode ("  filename … N events")
    # so we get the same visibility as the old per-file path.
    parsed, errors = process_files_list(new_files, con, verbose=True)

    # All-or-nothing: only mark files as processed after the batch insert
    # + matview refresh have committed. process_files_list commits itself.
    mark_files_processed(con, [f.name for f in new_files], rows_loaded=parsed)

    moved = 0
    for fpath in new_files:
        _move_to_loaded(fpath)
        moved += 1

    print(f"  ✓ {moved} file(s) loaded ({parsed:,} events) → moved to Loaded/")
    if errors:
        print(f"    ({errors} parse errors, ignored)")


# ── main loop ──────────────────────────────────────────────────

def watch_loop(con) -> None:
    ensure_processed_logs_table(con)
    ensure_jump_aggregates(con)
    LOADED_DIR.mkdir(exist_ok=True)

    print(f"Watching  : {LOGS_DIR}")
    print(f"Loaded dir: {LOADED_DIR}")
    print(f"Interval  : {POLL_INTERVAL}s")

    # Move any files the ETL already processed but left in place
    move_already_processed(con)

    print("Ready — waiting for new Journal*.log files…\n", flush=True)

    while True:
        try:
            new_files = find_new_files(con)
            if new_files:
                print(f"[{_now()}] Found {len(new_files)} new file(s):")
                load_batch(new_files, con)
                print(f"[{_now()}] Batch complete.\n", flush=True)
        except psycopg2.OperationalError as e:
            # Connection dropped — reconnect on next cycle
            print(f"[{_now()}] DB connection lost: {e} — reconnecting…", file=sys.stderr)
            try:
                con.close()
            except Exception:
                pass
            time.sleep(5)
            con = connect()
            ensure_processed_logs_table(con)
        except Exception as e:
            print(f"[{_now()}] Unexpected error: {e}", file=sys.stderr)

        time.sleep(POLL_INTERVAL)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


if __name__ == "__main__":
    con = connect()
    watch_loop(con)
