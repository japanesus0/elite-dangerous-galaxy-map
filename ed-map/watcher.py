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


def load_and_move(fpath: Path, con) -> None:
    """Parse one journal file, insert into PostgreSQL, move to Loaded/."""
    fname = fpath.name
    print(f"  → {fname}", flush=True)
    try:
        parsed, errors = process_files_list([fpath], con, verbose=True)
        mark_files_processed(con, [fname], rows_loaded=parsed)
        dest = LOADED_DIR / fname
        # If a file with the same name already exists in Loaded/, suffix it
        if dest.exists():
            stem   = fpath.stem
            suffix = fpath.suffix
            dest   = LOADED_DIR / f"{stem}_dup_{int(time.time())}{suffix}"
        shutil.move(str(fpath), str(dest))
        print(f"  ✓ {fname}: {parsed:,} events loaded → moved to Loaded/")
        if errors:
            print(f"    ({errors} parse errors, ignored)")
    except Exception as e:
        print(f"  ✗ {fname}: {e}", file=sys.stderr)
        # Don't mark as processed — will retry next poll cycle


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
                for fpath in new_files:
                    load_and_move(fpath, con)
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
