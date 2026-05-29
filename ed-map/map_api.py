#!/usr/bin/env python3
"""
Elite Dangerous — Galaxy Map API
=================================
FastAPI backend that serves jump/system data from PostgreSQL
and the Three.js map frontend.

Start:
    docker compose up elite-map
Then open: http://localhost:8051

Environment variables (set via .env or docker-compose):
    POSTGRES_HOST      default: localhost
    POSTGRES_PORT      default: 5432
    POSTGRES_DB        default: elite_dangerous
    POSTGRES_USER      default: elite
    POSTGRES_PASSWORD  default: elite_secret
    MAP_HOST           default: 0.0.0.0
    MAP_PORT           default: 8051
"""

import os
import time
from pathlib import Path
from typing import Optional

import psycopg2
import psycopg2.errors
import psycopg2.extras
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Elite Dangerous Galaxy Map API")

# Permissive CORS — the map is served same-origin in the bundled docker
# stack, but allowing cross-origin makes split deployments (dev frontend,
# prod backend) trivial. Tighten via ALLOWED_ORIGINS=... if you want.
_origins = os.environ.get("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins if o.strip()],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Vendored three.js + (next commit) split CSS / JS modules
_STATIC_DIR = Path(__file__).parent / "static"
if _STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

# ── DB connection ──────────────────────────────────────────────

def _db_cfg() -> dict:
    return {
        "host":     os.environ.get("POSTGRES_HOST",     "localhost"),
        "port":     int(os.environ.get("POSTGRES_PORT", "5432")),
        "dbname":   os.environ.get("POSTGRES_DB",       "elite_dangerous"),
        "user":     os.environ.get("POSTGRES_USER",     "elite"),
        "password": os.environ.get("POSTGRES_PASSWORD", "elite_secret"),
    }


def get_conn(retries: int = 10, delay: float = 3.0):
    """Return a psycopg2 connection, retrying until Postgres is ready."""
    for attempt in range(1, retries + 1):
        try:
            return psycopg2.connect(**_db_cfg())
        except psycopg2.OperationalError as e:
            if attempt == retries:
                raise
            print(f"  DB not ready ({attempt}/{retries}), retrying…")
            time.sleep(delay)


# ── SQL ────────────────────────────────────────────────────────
# Jump SQL is built dynamically in api_jumps() to support optional
# commander filtering.  See api_jumps() below.

def _build_stats_sql(commander: Optional[str] = None):
    """Build aggregate statistics SQL with optional commander filter."""
    if commander:
        j_w    = "WHERE j.source_file   IN (SELECT source_file FROM sessions WHERE fid = %s)"
        sc_and = "AND   sc.source_file  IN (SELECT source_file FROM sessions WHERE fid = %s)"
        b_w    = "WHERE b.source_file   IN (SELECT source_file FROM sessions WHERE fid = %s)"
        mi_w   = "WHERE mi.source_file  IN (SELECT source_file FROM sessions WHERE fid = %s)"
        se_w   = "WHERE se.source_file  IN (SELECT source_file FROM sessions WHERE fid = %s)"
        mc_w   = "WHERE mc.source_file  IN (SELECT source_file FROM sessions WHERE fid = %s)"
        mr_w   = "WHERE mr.source_file  IN (SELECT source_file FROM sessions WHERE fid = %s)"
        # 3 (jumps) + 2 (scans) + 2 (bounties) + 1 (missions) + 1 (sessions)
        #   + 1 (materials) + 1 (mining) = 11
        args   = (commander,) * 11
    else:
        j_w = sc_and = b_w = mi_w = se_w = mc_w = mr_w = ""
        args = ()

    sql = f"""
SELECT
    (SELECT COUNT(*)                               FROM jumps    j   {j_w})       AS total_jumps,
    (SELECT ROUND(SUM(j.jump_dist)::numeric, 1)    FROM jumps    j   {j_w})       AS total_ly,
    (SELECT COUNT(DISTINCT j.star_system)           FROM jumps    j   {j_w})       AS unique_systems,
    (SELECT COUNT(*)   FROM scans  sc WHERE sc.was_discovered = true {sc_and})    AS discoveries,
    (SELECT COUNT(*)   FROM scans  sc WHERE sc.planet_class ILIKE 'Earthlike%%' {sc_and}) AS earth_likes,
    (SELECT COUNT(*)                               FROM bounties  b   {b_w})      AS bounties,
    (SELECT COALESCE(SUM(b.total_reward), 0)        FROM bounties  b   {b_w})      AS bounty_credits,
    (SELECT COUNT(*)                               FROM missions  mi  {mi_w})     AS missions,
    (SELECT COUNT(*)                               FROM sessions  se  {se_w})     AS sessions,
    (SELECT COALESCE(SUM(mc.count), 0)              FROM materials_collected mc {mc_w}) AS materials_collected,
    (SELECT COUNT(*)                               FROM mining_refined mr {mr_w}) AS minerals_mined
"""
    return sql, args


# ── API endpoints ──────────────────────────────────────────────

@app.get("/api/health")
def api_health():
    """Liveness + DB-readiness probe.

    Always-present fields:
        status:   "ok" | "degraded" | "down"
        db:       "ok" | "error: ..."
        matview:  "ok" | "missing"

    Operational fields (best-effort — omitted on error):
        jump_count               total jumps in the DB
        last_jump_at             ISO8601 — most recent jump.timestamp
        last_processed_log_at    ISO8601 — most recent processed_logs row
        last_processed_file      filename of that row
        matview_last_refreshed   ISO8601 — pg_stat_all_tables.last_vacuum
                                 (CONCURRENTLY refresh records as vacuum-like)

    Returns HTTP 503 if the DB is unreachable, otherwise 200.
    """
    out = {"status": "ok", "db": "ok", "matview": "ok"}
    try:
        conn = get_conn(retries=1, delay=0.5)
    except Exception as e:
        return JSONResponse(
            {"status": "down", "db": f"error: {type(e).__name__}: {e}"},
            status_code=503,
        )
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")

            # Matview presence
            cur.execute("""
                SELECT 1 FROM pg_class
                WHERE relkind = 'm' AND relname = 'jump_aggregates'
            """)
            if cur.fetchone() is None:
                out["matview"] = "missing"
                out["status"]  = "degraded"

            # Operational counters — wrap each in its own try so a missing
            # table can't fail the whole probe.
            try:
                cur.execute("""
                    SELECT COUNT(*),
                           TO_CHAR(MAX(timestamp) AT TIME ZONE 'UTC',
                                   'YYYY-MM-DD"T"HH24:MI:SS"Z"')
                    FROM jumps
                """)
                cnt, last_ts = cur.fetchone()
                out["jump_count"]   = int(cnt or 0)
                out["last_jump_at"] = last_ts
            except Exception:
                conn.rollback()

            try:
                cur.execute("""
                    SELECT TO_CHAR(processed_at AT TIME ZONE 'UTC',
                                   'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
                           filename
                    FROM processed_logs
                    ORDER BY processed_at DESC
                    LIMIT 1
                """)
                row = cur.fetchone()
                if row:
                    out["last_processed_log_at"] = row[0]
                    out["last_processed_file"]   = row[1]
            except Exception:
                conn.rollback()

            try:
                # last_vacuum tracks REFRESH MATERIALIZED VIEW CONCURRENTLY;
                # plain REFRESH does not, so this can be NULL on a freshly
                # created matview that's never been concurrently refreshed.
                cur.execute("""
                    SELECT TO_CHAR(GREATEST(last_vacuum, last_autovacuum)
                                       AT TIME ZONE 'UTC',
                                   'YYYY-MM-DD"T"HH24:MI:SS"Z"')
                    FROM pg_stat_all_tables
                    WHERE relname = 'jump_aggregates'
                """)
                row = cur.fetchone()
                if row and row[0]:
                    out["matview_last_refreshed"] = row[0]
            except Exception:
                conn.rollback()
    finally:
        conn.close()
    return JSONResponse(out)


@app.get("/api/jumps")
def api_jumps(commander: Optional[str] = None):
    """All jumps enriched with discoveries, earth-likes, and bounties.

    Reads from the `jump_aggregates` materialized view, which is refreshed
    by the ETL/watcher after every load. Falls back to a live join over
    `jumps` if the view doesn't exist yet (e.g. on a partially-migrated DB).

    Optional query param:
        commander=<fid>  — only include jumps for this commander FID
    """
    if commander:
        cmd_filter = (
            "WHERE source_file IN ("
            "  SELECT source_file FROM sessions WHERE fid = %s"
            ")"
        )
        args = (commander,)
    else:
        cmd_filter = ""
        args = ()

    sql = f"""
SELECT
    TO_CHAR(jump_time AT TIME ZONE 'UTC',
            'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS timestamp,
    star_system,
    system_address,
    x, y, z,
    jump_dist,
    security,
    population,
    first_discoveries,
    disc_bodies,
    earth_likes,
    el_bodies,
    bounties_collected,
    bounty_credits,
    materials_collected,
    missions,
    sessions,
    minerals_mined
FROM jump_aggregates
{cmd_filter}
ORDER BY jump_time
"""

    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            try:
                cur.execute(sql, args)
                rows = cur.fetchall()
            except psycopg2.errors.UndefinedTable:
                # View hasn't been created yet — surface a clear error rather
                # than silently fall back to the slow path.
                conn.rollback()
                raise HTTPException(
                    status_code=503,
                    detail="jump_aggregates view not initialised — "
                           "run `docker compose run --rm elite-etl` once.",
                )
    finally:
        conn.close()

    # Convert Decimal → float for JSON serialisation
    result = []
    for r in rows:
        d = dict(r)
        for k in ("x", "y", "z", "jump_dist"):
            if d.get(k) is not None:
                d[k] = float(d[k])
        for k in ("bounty_credits", "materials_collected", "missions",
                  "sessions", "minerals_mined"):
            if d.get(k) is not None:
                d[k] = int(d[k])
        result.append(d)
    return JSONResponse(result)


@app.get("/api/stats")
def api_stats(commander: Optional[str] = None):
    """Aggregate statistics across all journal data, optionally filtered by commander FID."""
    sql, args = _build_stats_sql(commander)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            row = cur.fetchone()
    finally:
        conn.close()

    labels = [
        "total_jumps", "total_ly", "unique_systems",
        "discoveries", "earth_likes", "bounties", "bounty_credits",
        "missions", "sessions", "materials_collected",
        "minerals_mined",
    ]
    data = {}
    for i, label in enumerate(labels):
        v = row[i]
        if v is None:
            data[label] = 0
        elif hasattr(v, "__float__"):
            data[label] = float(v)
        else:
            data[label] = int(v)
    return JSONResponse(data)


@app.get("/api/commanders")
def api_commanders():
    """List all commanders in the database with jump counts."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    c.fid,
                    c.name,
                    TO_CHAR(c.first_seen AT TIME ZONE 'UTC', 'YYYY-MM-DD') AS first_seen,
                    TO_CHAR(c.last_seen  AT TIME ZONE 'UTC', 'YYYY-MM-DD') AS last_seen,
                    COUNT(DISTINCT j.jump_id)::INT                          AS jump_count
                FROM commanders c
                LEFT JOIN sessions s ON s.fid = c.fid
                LEFT JOIN jumps    j ON j.source_file = s.source_file
                GROUP BY c.fid, c.name, c.first_seen, c.last_seen
                ORDER BY c.name
            """)
            rows = cur.fetchall()
    finally:
        conn.close()
    return JSONResponse([dict(r) for r in rows])


@app.get("/api/system/{system_address}")
def api_system(system_address: int, visit: Optional[str] = None):
    """Detail drill-down for a single star system.

    Query params:
        visit=<ISO8601>  — optional. When provided, scope scans/bounties to
                           the single visit whose arrival is closest to this
                           timestamp (on or before). Without `visit`, the
                           *first* visit is used (prior behavior).
    """
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Jump info — pick the targeted visit
            if visit:
                cur.execute("""
                    SELECT
                        star_system, system_address,
                        ROUND(x::numeric, 2) AS x,
                        ROUND(y::numeric, 2) AS y,
                        ROUND(z::numeric, 2) AS z,
                        ROUND(SQRT(x*x + y*y + z*z)::numeric, 1) AS dist_from_sol_ly,
                        ROUND(jump_dist::numeric, 2)              AS jump_dist,
                        TO_CHAR(timestamp AT TIME ZONE 'UTC',
                                'YYYY-MM-DD HH24:MI "UTC"')       AS jump_time,
                        timestamp                                  AS arrival_ts,
                        security, population
                    FROM jumps
                    WHERE system_address = %s AND timestamp <= %s
                    ORDER BY timestamp DESC
                    LIMIT 1
                """, (system_address, visit))
            else:
                cur.execute("""
                    SELECT
                        star_system, system_address,
                        ROUND(x::numeric, 2) AS x,
                        ROUND(y::numeric, 2) AS y,
                        ROUND(z::numeric, 2) AS z,
                        ROUND(SQRT(x*x + y*y + z*z)::numeric, 1) AS dist_from_sol_ly,
                        ROUND(jump_dist::numeric, 2)              AS jump_dist,
                        TO_CHAR(timestamp AT TIME ZONE 'UTC',
                                'YYYY-MM-DD HH24:MI "UTC"')       AS jump_time,
                        timestamp                                  AS arrival_ts,
                        security, population
                    FROM jumps
                    WHERE system_address = %s
                    ORDER BY timestamp
                    LIMIT 1
                """, (system_address,))
            jump = cur.fetchone()
            if not jump:
                raise HTTPException(status_code=404, detail="System not found")

            arrival_ts = jump["arrival_ts"]
            # Compute the next-jump-out timestamp so scans / bounties are
            # bounded to THIS visit only (not all-time aggregates).
            cur.execute("""
                SELECT MIN(timestamp) AS ts
                FROM jumps
                WHERE timestamp > %s
            """, (arrival_ts,))
            dep_row = cur.fetchone()
            departure_ts = dep_row["ts"] if dep_row and dep_row["ts"] else None

            # Scans restricted to this visit's window
            cur.execute("""
                SELECT
                    body_name,
                    COALESCE(star_type, planet_class, 'Unknown') AS body_type,
                    was_discovered, was_mapped,
                    ROUND(distance_from_arrival::numeric, 1)     AS dist_ls,
                    landable, atmosphere
                FROM scans
                WHERE system_address = %s
                  AND timestamp >= %s
                  AND (%s::timestamptz IS NULL OR timestamp < %s::timestamptz)
                ORDER BY distance_from_arrival NULLS LAST
            """, (system_address, arrival_ts, departure_ts, departure_ts))
            scans = cur.fetchall()

            # Bounties earned during this same visit window
            cur.execute("""
                SELECT
                    TO_CHAR(b.timestamp AT TIME ZONE 'UTC', 'HH24:MI') AS time,
                    b.target_localised                                  AS ship,
                    b.victim_faction,
                    b.total_reward
                FROM bounties b
                WHERE b.timestamp >= %s
                  AND (%s::timestamptz IS NULL OR b.timestamp < %s::timestamptz)
                ORDER BY b.timestamp
            """, (arrival_ts, departure_ts, departure_ts))
            bounties = cur.fetchall()

            # Drop internal arrival_ts from the jump dict before returning
            jump = {k: v for k, v in jump.items() if k != "arrival_ts"}

    finally:
        conn.close()

    def clean(d):
        out = {}
        for k, v in d.items():
            if hasattr(v, "__float__"):
                out[k] = float(v)
            elif hasattr(v, "__int__") and not isinstance(v, bool):
                out[k] = int(v)
            else:
                out[k] = v
        return out

    return JSONResponse({
        "jump":     clean(dict(jump)),
        "scans":    [clean(dict(s)) for s in scans],
        "bounties": [clean(dict(b)) for b in bounties],
    })


@app.get("/api/loadouts")
def api_loadouts():
    """All loadouts in timestamp order.

    Used by the map frontend to resolve the current ship client-side via
    binary search, avoiding a per-second /api/ship fetch during playback.
    """
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    TO_CHAR(timestamp AT TIME ZONE 'UTC',
                            'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS timestamp,
                    ship, ship_name, ship_ident,
                    hull_health, unladen_mass, cargo_capacity,
                    max_jump_range, rebuy
                FROM loadouts
                ORDER BY timestamp
            """)
            rows = cur.fetchall()
    finally:
        conn.close()

    out = []
    for r in rows:
        d = dict(r)
        for k in ("hull_health", "unladen_mass", "max_jump_range"):
            if d.get(k) is not None:
                d[k] = float(d[k])
        for k in ("cargo_capacity", "rebuy"):
            if d.get(k) is not None:
                d[k] = int(d[k])
        out.append(d)
    return JSONResponse(out)


@app.get("/api/ship")
def api_ship(before: Optional[str] = None):
    """Most recent loadout (ship type + stats) at or before the given timestamp."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if before:
                cur.execute("""
                    SELECT ship, ship_name, ship_ident,
                           hull_health, unladen_mass, cargo_capacity,
                           max_jump_range, rebuy
                    FROM loadouts
                    WHERE timestamp <= %s
                    ORDER BY timestamp DESC
                    LIMIT 1
                """, (before,))
            else:
                cur.execute("""
                    SELECT ship, ship_name, ship_ident,
                           hull_health, unladen_mass, cargo_capacity,
                           max_jump_range, rebuy
                    FROM loadouts
                    ORDER BY timestamp DESC
                    LIMIT 1
                """)
            row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        return JSONResponse({"ship": None})

    d = dict(row)
    for k in ("hull_health", "unladen_mass", "max_jump_range"):
        if d.get(k) is not None:
            d[k] = float(d[k])
    for k in ("cargo_capacity", "rebuy"):
        if d.get(k) is not None:
            d[k] = int(d[k])
    return JSONResponse(d)


@app.get("/api/bounties/summary")
def api_bounties_summary(before: Optional[str] = None):
    """Aggregated bounty statistics: by ship, by faction, by year, totals.

    Optional query param:
        before=<ISO timestamp>  — only include bounties up to that moment
                                  (used by the map for real-time timeline filtering)
    """
    # Build an optional WHERE clause for the timestamp filter
    ts_filter = "WHERE timestamp <= %s" if before else ""
    ts_args   = (before,)              if before else ()

    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:

            # Totals
            cur.execute(f"""
                SELECT
                    COUNT(*)                                        AS total_kills,
                    COALESCE(SUM(total_reward), 0)                 AS total_credits,
                    ROUND(AVG(total_reward)::numeric)              AS avg_reward,
                    MAX(total_reward)                              AS max_reward,
                    COUNT(DISTINCT victim_faction)                 AS unique_factions,
                    COUNT(DISTINCT COALESCE(target_localised, target)) AS unique_ships
                FROM bounties {ts_filter}
            """, ts_args)
            totals = dict(cur.fetchone())

            # Ships killed — sorted by kill count
            cur.execute(f"""
                SELECT
                    COALESCE(target_localised, target, 'Unknown') AS ship,
                    COUNT(*)                                       AS kills,
                    COALESCE(SUM(total_reward), 0)                AS total_credits,
                    ROUND(AVG(total_reward)::numeric)             AS avg_reward
                FROM bounties {ts_filter}
                GROUP BY ship
                ORDER BY kills DESC
                LIMIT 40
            """, ts_args)
            by_ship = [dict(r) for r in cur.fetchall()]

            # Factions hunted — sorted by kill count
            cur.execute(f"""
                SELECT
                    COALESCE(victim_faction, 'Unknown') AS faction,
                    COUNT(*)                            AS kills,
                    COALESCE(SUM(total_reward), 0)      AS total_credits,
                    ROUND(AVG(total_reward)::numeric)   AS avg_reward
                FROM bounties {ts_filter}
                GROUP BY faction
                ORDER BY kills DESC
                LIMIT 25
            """, ts_args)
            by_faction = [dict(r) for r in cur.fetchall()]

            # Activity by year
            cur.execute(f"""
                SELECT
                    EXTRACT(YEAR FROM timestamp)::INT              AS year,
                    COUNT(*)                                       AS kills,
                    COALESCE(SUM(total_reward), 0)                AS total_credits
                FROM bounties {ts_filter}
                GROUP BY year
                ORDER BY year
            """, ts_args)
            by_year = [dict(r) for r in cur.fetchall()]

            # Most lucrative single bounty
            cur.execute(f"""
                SELECT
                    TO_CHAR(timestamp AT TIME ZONE 'UTC',
                            'YYYY-MM-DD HH24:MI "UTC"')           AS time,
                    COALESCE(target_localised, target, '?')       AS ship,
                    COALESCE(victim_faction, '?')                 AS faction,
                    total_reward
                FROM bounties {ts_filter}
                ORDER BY total_reward DESC NULLS LAST
                LIMIT 10
            """, ts_args)
            top_kills = [dict(r) for r in cur.fetchall()]

    finally:
        conn.close()

    def clean(d):
        out = {}
        for k, v in d.items():
            if v is None:
                out[k] = 0
            elif hasattr(v, '__float__') and not isinstance(v, (int, bool)):
                out[k] = float(v)
            elif hasattr(v, '__int__') and not isinstance(v, bool):
                out[k] = int(v)
            else:
                out[k] = v
        return out

    return JSONResponse({
        "totals":     clean(totals),
        "by_ship":    [clean(r) for r in by_ship],
        "by_faction": [clean(r) for r in by_faction],
        "by_year":    [clean(r) for r in by_year],
        "top_kills":  [clean(r) for r in top_kills],
    })


@app.get("/api/mining/summary")
def api_mining_summary(before: Optional[str] = None):
    """Aggregated mining statistics: by material, by year, totals.

    Optional query param:
        before=<ISO timestamp>  — only include events up to that moment
                                  (used by the map for timeline filtering)
    """
    ts_filter = "WHERE timestamp <= %s" if before else ""
    ts_args   = (before,)              if before else ()

    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:

            # Totals
            cur.execute(f"""
                SELECT
                    COUNT(*)                            AS total_refined,
                    COUNT(DISTINCT COALESCE(type_localised, type)) AS unique_materials
                FROM mining_refined {ts_filter}
            """, ts_args)
            totals = dict(cur.fetchone())

            # By material — sorted by refine count
            cur.execute(f"""
                SELECT
                    COALESCE(type_localised,
                             REPLACE(REPLACE(type, '$', ''), '_Name;', ''),
                             'Unknown')                AS material,
                    COUNT(*)                           AS count
                FROM mining_refined {ts_filter}
                GROUP BY material
                ORDER BY count DESC
                LIMIT 50
            """, ts_args)
            by_material = [dict(r) for r in cur.fetchall()]

            # Activity by year
            cur.execute(f"""
                SELECT
                    EXTRACT(YEAR FROM timestamp)::INT  AS year,
                    COUNT(*)                           AS count
                FROM mining_refined {ts_filter}
                GROUP BY year
                ORDER BY year
            """, ts_args)
            by_year = [dict(r) for r in cur.fetchall()]

            # Most recent 15 refining events
            cur.execute(f"""
                SELECT
                    TO_CHAR(timestamp AT TIME ZONE 'UTC',
                            'YYYY-MM-DD HH24:MI "UTC"')                    AS time,
                    COALESCE(type_localised,
                             REPLACE(REPLACE(type, '$', ''), '_Name;', ''),
                             'Unknown')                                     AS material
                FROM mining_refined {ts_filter}
                ORDER BY timestamp DESC
                LIMIT 15
            """, ts_args)
            recent = [dict(r) for r in cur.fetchall()]

    finally:
        conn.close()

    def clean(d):
        out = {}
        for k, v in d.items():
            if v is None:
                out[k] = 0
            elif hasattr(v, '__int__') and not isinstance(v, bool):
                out[k] = int(v)
            else:
                out[k] = v
        return out

    return JSONResponse({
        "totals":      clean(totals),
        "by_material": [clean(r) for r in by_material],
        "by_year":     [clean(r) for r in by_year],
        "recent":      [clean(r) for r in recent],
    })


# ── Static files ───────────────────────────────────────────────

@app.get("/")
def serve_map():
    """Serve the Three.js galaxy map."""
    html = Path(__file__).parent / "map.html"
    if not html.exists():
        return JSONResponse({"error": "map.html not found"}, status_code=404)
    return FileResponse(html, media_type="text/html")


# ── Entry point ────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "map_api:app",
        host=os.environ.get("MAP_HOST", "0.0.0.0"),
        port=int(os.environ.get("MAP_PORT", "8051")),
        reload=False,
    )
