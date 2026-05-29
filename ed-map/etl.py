#!/usr/bin/env python3
"""
Elite Dangerous Journal Log ETL → PostgreSQL
=============================================
Parses all Journal*.log files and loads events into PostgreSQL.

Usage:
    python etl.py [--logs-dir PATH] [--rebuild] [--verbose]

Options:
    --logs-dir  Folder containing Journal*.log files (default: ../)
    --rebuild   Drop all tables and start fresh (use after schema changes)
    --verbose   Print per-file progress

Environment variables (set via .env or docker-compose):
    POSTGRES_HOST      default: localhost
    POSTGRES_PORT      default: 5432
    POSTGRES_DB        default: elite_dangerous
    POSTGRES_USER      default: elite
    POSTGRES_PASSWORD  default: elite_secret
    ED_LOGS_DIR        overrides --logs-dir
"""

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
import psycopg2.extras

# ── DB connection ──────────────────────────────────────────────

def db_config() -> dict:
    return {
        "host":     os.environ.get("POSTGRES_HOST",     "localhost"),
        "port":     int(os.environ.get("POSTGRES_PORT", "5432")),
        "dbname":   os.environ.get("POSTGRES_DB",       "elite_dangerous"),
        "user":     os.environ.get("POSTGRES_USER",     "elite"),
        "password": os.environ.get("POSTGRES_PASSWORD", "elite_secret"),
    }


def connect(retries: int = 10, delay: float = 3.0):
    """Connect to PostgreSQL, retrying until the server is ready."""
    cfg = db_config()
    for attempt in range(1, retries + 1):
        try:
            con = psycopg2.connect(**cfg)
            con.autocommit = False
            return con
        except psycopg2.OperationalError as e:
            if attempt == retries:
                print(f"Cannot connect to PostgreSQL after {retries} attempts: {e}", file=sys.stderr)
                sys.exit(1)
            print(f"  Waiting for PostgreSQL ({attempt}/{retries})…", flush=True)
            time.sleep(delay)


# ── Processed-log tracking ─────────────────────────────────────

def ensure_processed_logs_table(con) -> None:
    """Create the processed_logs table if it doesn't exist yet."""
    with con.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS processed_logs (
                filename     TEXT PRIMARY KEY,
                processed_at TIMESTAMPTZ DEFAULT NOW(),
                rows_loaded  BIGINT      DEFAULT 0
            )
        """)
    con.commit()


def get_processed_files(con) -> set:
    """Return the set of filenames already recorded in processed_logs."""
    try:
        with con.cursor() as cur:
            cur.execute("SELECT filename FROM processed_logs")
            return {row[0] for row in cur.fetchall()}
    except Exception:
        return set()


def mark_files_processed(con, filenames: list, rows_loaded: int = 0) -> None:
    """Upsert one row per filename into processed_logs."""
    if not filenames:
        return
    with con.cursor() as cur:
        for fname in filenames:
            cur.execute("""
                INSERT INTO processed_logs (filename, rows_loaded)
                VALUES (%s, %s)
                ON CONFLICT (filename) DO UPDATE SET
                    processed_at = NOW(),
                    rows_loaded  = EXCLUDED.rows_loaded
            """, (fname, rows_loaded))
    con.commit()


# ── Helpers ────────────────────────────────────────────────────

def parse_ts(ts_str):
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except Exception:
        return None


def row_id(*parts) -> str:
    key = "|".join(str(p) for p in parts)
    return hashlib.md5(key.encode()).hexdigest()[:16]


# ── Per-event parsers ──────────────────────────────────────────

def parse_loadgame(ev, src):
    return {"sessions": [{
        "session_id":    row_id(src, ev.get("timestamp", "")),
        "timestamp":     parse_ts(ev.get("timestamp")),
        "fid":           ev.get("FID"),
        "commander":     ev.get("Commander"),
        "ship":          ev.get("Ship"),
        "ship_localised":ev.get("Ship_Localised"),
        "ship_id":       ev.get("ShipID"),
        "ship_name":     ev.get("ShipName"),
        "ship_ident":    ev.get("ShipIdent"),
        "fuel_level":    ev.get("FuelLevel"),
        "fuel_capacity": ev.get("FuelCapacity"),
        "game_mode":     ev.get("GameMode"),
        "game_group":    ev.get("Group"),
        "credits":       ev.get("Credits"),
        "horizons":      ev.get("Horizons"),
        "odyssey":       ev.get("Odyssey"),
        "game_version":  ev.get("gameversion"),
        "source_file":   src,
    }]}


def parse_commander(ev, src):
    fid = ev.get("FID")
    if not fid:
        return {}
    return {"commanders_raw": [{
        "fid":       fid,
        "name":      ev.get("Name"),
        "timestamp": parse_ts(ev.get("timestamp")),
    }]}


def parse_rank(ev, src):
    return {"ranks": [{
        "id":           row_id(src, ev.get("timestamp", "")),
        "timestamp":    parse_ts(ev.get("timestamp")),
        "fid":          None,
        "combat":       ev.get("Combat"),
        "trade":        ev.get("Trade"),
        "explore":      ev.get("Explore"),
        "soldier":      ev.get("Soldier"),
        "exobiologist": ev.get("Exobiologist"),
        "empire":       ev.get("Empire"),
        "federation":   ev.get("Federation"),
        "cqc":          ev.get("CQC"),
        "source_file":  src,
    }]}


def _pos(ev):
    p = ev.get("StarPos") or []
    return (p[0] if len(p) > 0 else None,
            p[1] if len(p) > 1 else None,
            p[2] if len(p) > 2 else None)


def _system_row(ev, ts):
    x, y, z = _pos(ev)
    return {
        "system_address": ev.get("SystemAddress"),
        "star_system":    ev.get("StarSystem"),
        "x": x, "y": y, "z": z,
        "allegiance":     ev.get("SystemAllegiance"),
        "economy":        ev.get("SystemEconomy_Localised") or ev.get("SystemEconomy"),
        "second_economy": ev.get("SystemSecondEconomy_Localised") or ev.get("SystemSecondEconomy"),
        "government":     ev.get("SystemGovernment_Localised") or ev.get("SystemGovernment"),
        "security":       ev.get("SystemSecurity_Localised") or ev.get("SystemSecurity"),
        "population":     ev.get("Population"),
        "first_visited":  ts,
        "last_visited":   ts,
        "visit_count":    1,
    }


def _faction_rows(ev, ts, source_event, source_id):
    rows = []
    for f in ev.get("Factions") or []:
        rows.append({
            # Include source_event in the id so the same faction reported by
            # FSDJump *and* Location at the same source_id don't collide.
            "id":             row_id(source_event, source_id, f.get("Name", "")),
            "source_event":   source_event,
            "source_id":      source_id,
            "system_address": ev.get("SystemAddress"),
            "timestamp":      ts,
            "faction_name":   f.get("Name"),
            "faction_state":  f.get("FactionState"),
            "government":     f.get("Government"),
            "influence":      f.get("Influence"),
            "allegiance":     f.get("Allegiance"),
            "happiness":      f.get("Happiness_Localised") or f.get("Happiness"),
            "my_reputation":  f.get("MyReputation"),
        })
    return rows


def parse_fsdjump(ev, src):
    ts = parse_ts(ev.get("timestamp"))
    x, y, z = _pos(ev)
    jump_id = row_id(ev.get("timestamp", ""), str(ev.get("SystemAddress", "")))
    return {
        "jumps": [{
            "jump_id":        jump_id,
            "timestamp":      ts,
            "star_system":    ev.get("StarSystem"),
            "system_address": ev.get("SystemAddress"),
            "x": x, "y": y, "z": z,
            "body":           ev.get("Body"),
            "body_id":        ev.get("BodyID"),
            "body_type":      ev.get("BodyType"),
            "jump_dist":      ev.get("JumpDist"),
            "fuel_used":      ev.get("FuelUsed"),
            "fuel_level":     ev.get("FuelLevel"),
            "allegiance":     ev.get("SystemAllegiance"),
            "economy":        ev.get("SystemEconomy_Localised") or ev.get("SystemEconomy"),
            "government":     ev.get("SystemGovernment_Localised") or ev.get("SystemGovernment"),
            "security":       ev.get("SystemSecurity_Localised") or ev.get("SystemSecurity"),
            "population":     ev.get("Population"),
            "powerplay_state":ev.get("PowerplayState"),
            "taxi":           ev.get("Taxi"),
            "multicrew":      ev.get("Multicrew"),
            "source_file":    src,
        }],
        "jump_powers":      [{"jump_id": jump_id, "power": p} for p in (ev.get("Powers") or [])],
        "star_systems_raw": [_system_row(ev, ts)],
        "system_factions":  _faction_rows(ev, ts, "FSDJump", jump_id),
    }


def parse_location(ev, src):
    ts = parse_ts(ev.get("timestamp"))
    x, y, z = _pos(ev)
    loc_id = row_id(ev.get("timestamp", ""), src)
    return {
        "locations": [{
            "location_id":    loc_id,
            "timestamp":      ts,
            "star_system":    ev.get("StarSystem"),
            "system_address": ev.get("SystemAddress"),
            "x": x, "y": y, "z": z,
            "body":           ev.get("Body"),
            "body_id":        ev.get("BodyID"),
            "body_type":      ev.get("BodyType"),
            "docked":         ev.get("Docked"),
            "station_name":   ev.get("StationName"),
            "station_type":   ev.get("StationType"),
            "market_id":      ev.get("MarketID"),
            "dist_from_star": ev.get("DistFromStarLS"),
            "allegiance":     ev.get("SystemAllegiance"),
            "economy":        ev.get("SystemEconomy_Localised") or ev.get("SystemEconomy"),
            "government":     ev.get("SystemGovernment_Localised") or ev.get("SystemGovernment"),
            "security":       ev.get("SystemSecurity_Localised") or ev.get("SystemSecurity"),
            "population":     ev.get("Population"),
            "source_file":    src,
        }],
        "star_systems_raw": [_system_row(ev, ts)],
        "system_factions":  _faction_rows(ev, ts, "Location", loc_id),
    }


def parse_docked(ev, src):
    ts = parse_ts(ev.get("timestamp"))
    market_id = ev.get("MarketID")
    dock_id = row_id(ev.get("timestamp", ""), src, str(market_id or ""))
    station = None
    if market_id:
        station = {
            "market_id":      market_id,
            "station_name":   ev.get("StationName"),
            "station_type":   ev.get("StationType"),
            "star_system":    ev.get("StarSystem"),
            "system_address": ev.get("SystemAddress"),
            "allegiance":     ev.get("StationAllegiance"),
            "government":     ev.get("StationGovernment_Localised") or ev.get("StationGovernment"),
            "economy":        ev.get("StationEconomy_Localised") or ev.get("StationEconomy"),
            "dist_from_star": ev.get("DistFromStarLS"),
            "first_docked":   ts,
            "last_docked":    ts,
            "dock_count":     1,
        }
    return {
        "docked": [{
            "dock_id":        dock_id,
            "timestamp":      ts,
            "station_name":   ev.get("StationName"),
            "station_type":   ev.get("StationType"),
            "star_system":    ev.get("StarSystem"),
            "system_address": ev.get("SystemAddress"),
            "market_id":      market_id,
            "allegiance":     ev.get("StationAllegiance"),
            "government":     ev.get("StationGovernment_Localised") or ev.get("StationGovernment"),
            "economy":        ev.get("StationEconomy_Localised") or ev.get("StationEconomy"),
            "dist_from_star": ev.get("DistFromStarLS"),
            "active_fine":    ev.get("ActiveFine"),
            "taxi":           ev.get("Taxi"),
            "multicrew":      ev.get("Multicrew"),
            "source_file":    src,
        }],
        "stations_raw": [station] if station else [],
    }


def parse_missionaccepted(ev, src):
    return {"missions": [{
        "mission_id":          ev.get("MissionID"),
        "timestamp":           parse_ts(ev.get("timestamp")),
        "faction":             ev.get("Faction"),
        "name":                ev.get("Name"),
        "localised_name":      ev.get("LocalisedName"),
        "target_type":         ev.get("TargetType_Localised") or ev.get("TargetType"),
        "target_faction":      ev.get("TargetFaction"),
        "kill_count":          ev.get("KillCount"),
        "destination_system":  ev.get("DestinationSystem"),
        "destination_station": ev.get("DestinationStation"),
        "expiry":              parse_ts(ev.get("Expiry")),
        "wing":                ev.get("Wing"),
        "influence":           ev.get("Influence"),
        "reputation":          ev.get("Reputation"),
        "reward":              ev.get("Reward"),
        "source_file":         src,
    }]}


def parse_missioncompleted(ev, src):
    return {"mission_completions": [{
        "id":                  row_id(ev.get("timestamp", ""), str(ev.get("MissionID", ""))),
        "mission_id":          ev.get("MissionID"),
        "timestamp":           parse_ts(ev.get("timestamp")),
        "faction":             ev.get("Faction"),
        "name":                ev.get("Name"),
        "kill_count":          ev.get("KillCount"),
        "destination_system":  ev.get("DestinationSystem"),
        "destination_station": ev.get("DestinationStation"),
        "reward":              ev.get("Reward"),
        "source_file":         src,
    }]}


def parse_bounty(ev, src):
    ts = parse_ts(ev.get("timestamp"))
    bounty_id = row_id(ev.get("timestamp", ""), src, ev.get("Target", ""))
    return {
        "bounties": [{
            "bounty_id":       bounty_id,
            "timestamp":       ts,
            "target":          ev.get("Target"),
            "target_localised":ev.get("Target_Localised"),
            "total_reward":    ev.get("TotalReward"),
            "victim_faction":  ev.get("VictimFaction"),
            "source_file":     src,
        }],
        "bounty_rewards": [
            {"bounty_id": bounty_id, "faction": r.get("Faction"), "reward": r.get("Reward")}
            for r in (ev.get("Rewards") or [])
        ],
    }


def parse_scan(ev, src):
    return {"scans": [{
        "scan_id":               row_id(ev.get("timestamp", ""), str(ev.get("BodyID", "")), src),
        "timestamp":             parse_ts(ev.get("timestamp")),
        "scan_type":             ev.get("ScanType"),
        "body_name":             ev.get("BodyName"),
        "body_id":               ev.get("BodyID"),
        "star_system":           ev.get("StarSystem"),
        "system_address":        ev.get("SystemAddress"),
        "distance_from_arrival": ev.get("DistanceFromArrivalLS"),
        "star_type":             ev.get("StarType"),
        "subclass":              ev.get("Subclass"),
        "stellar_mass":          ev.get("StellarMass"),
        "radius":                ev.get("Radius"),
        "surface_temp":          ev.get("SurfaceTemperature"),
        "luminosity":            ev.get("Luminosity"),
        "age_my":                ev.get("Age_MY"),
        "planet_class":          ev.get("PlanetClass"),
        "mass_em":               ev.get("MassEM"),
        "landable":              ev.get("Landable"),
        "atmosphere":            ev.get("Atmosphere"),
        "volcanism":             ev.get("Volcanism"),
        "surface_gravity":       ev.get("SurfaceGravity"),
        "surface_pressure":      ev.get("SurfacePressure"),
        "tidal_lock":            ev.get("TidalLock"),
        "semi_major_axis":       ev.get("SemiMajorAxis"),
        "eccentricity":          ev.get("Eccentricity"),
        "orbital_incl":          ev.get("OrbitalInclination"),
        "orbital_period":        ev.get("OrbitalPeriod"),
        "rotation_period":       ev.get("RotationPeriod"),
        "axial_tilt":            ev.get("AxialTilt"),
        "was_discovered":        ev.get("WasDiscovered"),
        "was_mapped":            ev.get("WasMapped"),
        "source_file":           src,
    }]}


def parse_materialcollected(ev, src):
    return {"materials_collected": [{
        "id":             row_id(ev.get("timestamp", ""), src, ev.get("Name", "")),
        "timestamp":      parse_ts(ev.get("timestamp")),
        "category":       ev.get("Category"),
        "name":           ev.get("Name"),
        "name_localised": ev.get("Name_Localised"),
        "count":          ev.get("Count"),
        "source_file":    src,
    }]}


def parse_miningrefined(ev, src):
    return {"mining_refined": [{
        "id":             row_id(ev.get("timestamp", ""), src),
        "timestamp":      parse_ts(ev.get("timestamp")),
        "type":           ev.get("Type"),
        "type_localised": ev.get("Type_Localised"),
        "source_file":    src,
    }]}


def parse_engineercraft(ev, src):
    ts = parse_ts(ev.get("timestamp"))
    craft_id = row_id(ev.get("timestamp", ""), src, ev.get("Slot", ""))
    return {
        "engineer_crafts": [{
            "craft_id":                      craft_id,
            "timestamp":                     ts,
            "slot":                          ev.get("Slot"),
            "module":                        ev.get("Module"),
            "engineer":                      ev.get("Engineer"),
            "engineer_id":                   ev.get("EngineerID"),
            "blueprint_id":                  ev.get("BlueprintID"),
            "blueprint_name":                ev.get("BlueprintName"),
            "level":                         ev.get("Level"),
            "quality":                       ev.get("Quality"),
            "experimental_effect":           ev.get("ExperimentalEffect"),
            "experimental_effect_localised": ev.get("ExperimentalEffect_Localised"),
            "source_file":                   src,
        }],
        "engineer_craft_ingredients": [
            {"craft_id": craft_id, "name": i.get("Name"),
             "name_localised": i.get("Name_Localised"), "count": i.get("Count")}
            for i in (ev.get("Ingredients") or [])
        ],
        "engineer_craft_modifiers": [
            {"craft_id": craft_id, "label": m.get("Label"),
             "value": m.get("Value"), "original_value": m.get("OriginalValue"),
             "less_is_good": bool(m.get("LessIsGood", 0))}
            for m in (ev.get("Modifiers") or [])
        ],
    }


def parse_loadout(ev, src):
    ts = parse_ts(ev.get("timestamp"))
    loadout_id = row_id(ev.get("timestamp", ""), src, str(ev.get("ShipID", "")))
    fuel = ev.get("FuelCapacity") or {}
    modules = []
    for m in (ev.get("Modules") or []):
        eng = m.get("Engineering") or {}
        modules.append({
            "loadout_id":          loadout_id,
            "slot":                m.get("Slot"),
            "item":                m.get("Item"),
            "is_on":               m.get("On"),
            "priority":            m.get("Priority"),
            "health":              m.get("Health"),
            "value":               m.get("Value"),
            "engineer":            eng.get("Engineer"),
            "blueprint_name":      eng.get("BlueprintName"),
            "blueprint_level":     eng.get("Level"),
            "blueprint_quality":   eng.get("Quality"),
            "experimental_effect": eng.get("ExperimentalEffect"),
        })
    return {
        "loadouts": [{
            "loadout_id":     loadout_id,
            "timestamp":      ts,
            "ship":           ev.get("Ship"),
            "ship_id":        ev.get("ShipID"),
            "ship_name":      ev.get("ShipName"),
            "ship_ident":     ev.get("ShipIdent"),
            "hull_value":     ev.get("HullValue"),
            "modules_value":  ev.get("ModulesValue"),
            "hull_health":    ev.get("HullHealth"),
            "unladen_mass":   ev.get("UnladenMass"),
            "cargo_capacity": ev.get("CargoCapacity"),
            "max_jump_range": ev.get("MaxJumpRange"),
            "fuel_main":      fuel.get("Main") if isinstance(fuel, dict) else None,
            "fuel_reserve":   fuel.get("Reserve") if isinstance(fuel, dict) else None,
            "rebuy":          ev.get("Rebuy"),
            "source_file":    src,
        }],
        "ship_modules": modules,
    }


def parse_fsssignaldiscovered(ev, src):
    sn = ev.get("SignalName", "")
    # Frontier emits an explicit SignalType (e.g. "Combat", "ResourceExtraction")
    # for known signal categories. Older logs only have SignalName, sometimes as
    # an opaque "$..._Name;" symbol — fall back to the localised text in that case.
    signal_type = ev.get("SignalType")
    if not signal_type and sn.startswith("$"):
        signal_type = ev.get("SignalName_Localised")
    return {"fss_signals": [{
        "id":                    row_id(ev.get("timestamp", ""), src, sn),
        "timestamp":             parse_ts(ev.get("timestamp")),
        "system_address":        ev.get("SystemAddress"),
        "signal_name":           sn,
        "signal_name_localised": ev.get("SignalName_Localised"),
        "signal_type":           signal_type,
        "source_file":           src,
    }]}


# ── Dispatch table ─────────────────────────────────────────────

EVENT_PARSERS = {
    "LoadGame":            parse_loadgame,
    "Commander":           parse_commander,
    "Rank":                parse_rank,
    "FSDJump":             parse_fsdjump,
    "Location":            parse_location,
    "Docked":              parse_docked,
    "MissionAccepted":     parse_missionaccepted,
    "MissionCompleted":    parse_missioncompleted,
    "Bounty":              parse_bounty,
    "Scan":                parse_scan,
    "MaterialCollected":   parse_materialcollected,
    "MiningRefined":       parse_miningrefined,
    "EngineerCraft":       parse_engineercraft,
    "Loadout":             parse_loadout,
    "FSSSignalDiscovered": parse_fsssignaldiscovered,
}

SIMPLE_TABLES = [
    "sessions", "ranks", "jumps", "jump_powers", "locations",
    "system_factions", "docked", "missions", "mission_completions",
    "bounties", "bounty_rewards", "scans", "materials_collected",
    "mining_refined", "engineer_crafts", "engineer_craft_ingredients",
    "engineer_craft_modifiers", "loadouts", "ship_modules", "fss_signals",
]

ALL_TABLES = SIMPLE_TABLES + ["star_systems", "stations", "commanders"]


# ── Database operations ────────────────────────────────────────

def rebuild_schema(con):
    """Drop all tables and recreate from schema.sql."""
    schema_path = Path(__file__).parent / "schema.sql"
    schema_sql = schema_path.read_text()
    with con.cursor() as cur:
        print("  Dropping all tables…")
        for table in reversed(ALL_TABLES):
            cur.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
        print("  Recreating schema…")
        cur.execute(schema_sql)
    con.commit()


def bulk_insert(cur, table: str, rows: list):
    """Bulk insert rows (list of dicts) using execute_values, ignoring conflicts."""
    rows = [r for r in rows if r is not None]
    if not rows:
        return 0
    cols = list(rows[0].keys())
    col_str = ", ".join(cols)
    values = [[r.get(c) for c in cols] for r in rows]
    sql = f"INSERT INTO {table} ({col_str}) VALUES %s ON CONFLICT DO NOTHING"
    psycopg2.extras.execute_values(cur, sql, values, page_size=500)
    return len(rows)


def upsert_star_systems(cur, rows: list):
    """Insert or update star systems, incrementing visit_count.

    Deduplicates the batch by system_address before sending to PostgreSQL —
    execute_values cannot update the same row twice in a single statement.
    visit_count is set to the number of appearances in this batch so the
    conflict clause can do  visit_count + EXCLUDED.visit_count  correctly.
    """
    rows = [r for r in rows if r and r.get("system_address")]
    if not rows:
        return

    # Count how many times each system appears in this batch
    counts: dict = {}
    for r in rows:
        counts[r["system_address"]] = counts.get(r["system_address"], 0) + 1

    # Keep only the row with the latest last_visited per system
    seen: dict = {}
    for r in rows:
        k = r["system_address"]
        cur_ts  = r.get("last_visited")
        prev_ts = seen[k].get("last_visited") if k in seen else None
        if k not in seen or (cur_ts and (prev_ts is None or cur_ts > prev_ts)):
            seen[k] = r

    # Stamp the actual visit count for this batch onto each deduplicated row
    deduped = []
    for k, r in seen.items():
        r = dict(r)
        r["visit_count"] = counts[k]
        deduped.append(r)

    cols   = list(deduped[0].keys())
    values = [[r.get(c) for c in cols] for r in deduped]
    sql = """
        INSERT INTO star_systems ({cols})
        VALUES %s
        ON CONFLICT (system_address) DO UPDATE SET
            last_visited = GREATEST(star_systems.last_visited, EXCLUDED.last_visited),
            visit_count  = star_systems.visit_count + EXCLUDED.visit_count,
            x = COALESCE(star_systems.x, EXCLUDED.x),
            y = COALESCE(star_systems.y, EXCLUDED.y),
            z = COALESCE(star_systems.z, EXCLUDED.z)
    """.format(cols=", ".join(cols))
    psycopg2.extras.execute_values(cur, sql, values, page_size=500)
    print(f"  {'star_systems':<38} {len(deduped):>8,} rows  ({sum(counts.values()):,} raw)")


def upsert_stations(cur, rows: list):
    """Insert or update stations, incrementing dock_count."""
    rows = [r for r in rows if r and r.get("market_id")]
    if not rows:
        return

    # Count dockings per station in this batch
    counts: dict = {}
    for r in rows:
        counts[r["market_id"]] = counts.get(r["market_id"], 0) + 1

    # Keep latest-docked row per station
    seen: dict = {}
    for r in rows:
        k = r["market_id"]
        cur_ts  = r.get("last_docked")
        prev_ts = seen[k].get("last_docked") if k in seen else None
        if k not in seen or (cur_ts and (prev_ts is None or cur_ts > prev_ts)):
            seen[k] = r

    deduped = []
    for k, r in seen.items():
        r = dict(r)
        r["dock_count"] = counts[k]
        deduped.append(r)

    cols   = list(deduped[0].keys())
    values = [[r.get(c) for c in cols] for r in deduped]
    sql = """
        INSERT INTO stations ({cols})
        VALUES %s
        ON CONFLICT (market_id) DO UPDATE SET
            last_docked = GREATEST(stations.last_docked, EXCLUDED.last_docked),
            dock_count  = stations.dock_count + EXCLUDED.dock_count
    """.format(cols=", ".join(cols))
    psycopg2.extras.execute_values(cur, sql, values, page_size=500)
    print(f"  {'stations':<38} {len(deduped):>8,} rows  ({sum(counts.values()):,} raw)")


def ensure_jump_aggregates(con) -> None:
    """Create the jump_aggregates materialized view if it doesn't exist yet.

    Lets existing databases pick up the view without a full --rebuild —
    schema.sql is only re-applied to a fresh postgres volume on first boot.
    """
    schema_path = Path(__file__).parent / "schema.sql"
    sql = schema_path.read_text()
    # Pull out only the materialized-view block (everything from the marker
    # comment to the end of the file). Cheap and robust enough.
    marker = "-- jump_aggregates"
    idx = sql.find(marker)
    if idx == -1:
        return
    matview_sql = sql[idx:]
    with con.cursor() as cur:
        cur.execute(matview_sql)
    con.commit()


def refresh_jump_aggregates(con, *, concurrent: bool = True) -> None:
    """Refresh the jump_aggregates matview after a load.

    Uses CONCURRENTLY so the view stays queryable during the refresh
    (the unique index on jump_id makes that legal). Falls back to a
    plain REFRESH if the view was just created and is still empty —
    Postgres rejects REFRESH CONCURRENTLY on a never-populated view.
    """
    ensure_jump_aggregates(con)
    print("  Refreshing jump_aggregates …", flush=True)
    t0 = time.time()
    with con.cursor() as cur:
        cur.execute("SELECT relispopulated FROM pg_class WHERE relname = 'jump_aggregates'")
        row = cur.fetchone()
        populated = bool(row and row[0])
        mode = "CONCURRENTLY" if (concurrent and populated) else ""
        cur.execute(f"REFRESH MATERIALIZED VIEW {mode} jump_aggregates")
    con.commit()
    print(f"  jump_aggregates refreshed in {time.time() - t0:.1f}s", flush=True)


def upsert_commanders(cur, rows: list):
    """Insert or update commanders, tracking first/last seen."""
    rows = [r for r in rows if r and r.get("fid")]
    if not rows:
        return

    # Deduplicate by fid — track both the earliest and latest timestamp
    by_fid: dict = {}
    for r in rows:
        k  = r["fid"]
        ts = r.get("timestamp")
        if k not in by_fid:
            by_fid[k] = {"fid": k, "name": r["name"], "min_ts": ts, "max_ts": ts}
        else:
            if ts and (by_fid[k]["min_ts"] is None or ts < by_fid[k]["min_ts"]):
                by_fid[k]["min_ts"] = ts
            if ts and (by_fid[k]["max_ts"] is None or ts > by_fid[k]["max_ts"]):
                by_fid[k]["max_ts"] = ts

    sql = """
        INSERT INTO commanders (fid, name, first_seen, last_seen)
        VALUES %s
        ON CONFLICT (fid) DO UPDATE SET
            last_seen = GREATEST(commanders.last_seen, EXCLUDED.last_seen)
    """
    values = [(v["fid"], v["name"], v["min_ts"], v["max_ts"]) for v in by_fid.values()]
    psycopg2.extras.execute_values(cur, sql, values, page_size=500)
    print(f"  {'commanders':<38} {len(by_fid):>8,} rows  ({len(rows):,} raw)")


# ── Main ETL ───────────────────────────────────────────────────

def process_files_list(file_paths: list, con, verbose: bool = False) -> tuple:
    """Parse a list of journal log Path objects and load into PostgreSQL.

    Returns (total_events_parsed, total_errors).
    Shared by run_etl (batch CLI) and watcher.py (incremental).
    """
    acc = {t: [] for t in SIMPLE_TABLES}
    acc["star_systems_raw"] = []
    acc["stations_raw"]     = []
    acc["commanders_raw"]   = []

    parsed = errors = 0

    for fpath in file_paths:
        fname = fpath.name
        if verbose:
            print(f"  {fname}", end=" … ", flush=True)
        file_count = 0
        try:
            with open(fpath, encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ev = json.loads(line)
                    except json.JSONDecodeError:
                        errors += 1
                        continue
                    parser = EVENT_PARSERS.get(ev.get("event", ""))
                    if parser:
                        try:
                            for table, rows in parser(ev, fname).items():
                                if rows:
                                    acc[table].extend(rows)
                            file_count += 1
                        except Exception as e:
                            errors += 1
                            if verbose:
                                print(f"\n    [{ev.get('event')}] {e}", file=sys.stderr)
        except Exception as e:
            print(f"\n  ERROR reading {fname}: {e}", file=sys.stderr)
        parsed += file_count
        if verbose:
            print(f"{file_count} events")

    if parsed == 0 and not any(acc[t] for t in acc):
        return 0, errors

    print(f"  Writing {parsed:,} events to PostgreSQL…")
    with con.cursor() as cur:
        total_rows = 0
        for table in SIMPLE_TABLES:
            n = bulk_insert(cur, table, acc[table])
            if n:
                print(f"    {table:<36} {n:>8,} rows")
                total_rows += n
        upsert_star_systems(cur, acc["star_systems_raw"])
        upsert_stations(cur, acc["stations_raw"])
        upsert_commanders(cur, acc["commanders_raw"])
    con.commit()

    # Keep the precomputed per-jump summary in sync after every load
    refresh_jump_aggregates(con)

    return parsed, errors


def _print_quick_stats(con) -> None:
    """Print aggregate stats across all loaded data."""
    print("\n=== Quick Stats ===")
    queries = [
        ("Play sessions",        "SELECT COUNT(*) FROM sessions"),
        ("Total jumps",          "SELECT COUNT(*) FROM jumps"),
        ("Unique systems",       "SELECT COUNT(*) FROM star_systems"),
        ("Total ly travelled",   "SELECT ROUND(SUM(jump_dist)::numeric, 1) FROM jumps"),
        ("Longest jump (ly)",    "SELECT ROUND(MAX(jump_dist)::numeric, 2) FROM jumps"),
        ("Missions accepted",    "SELECT COUNT(*) FROM missions"),
        ("Missions completed",   "SELECT COUNT(*) FROM mission_completions"),
        ("Bounties collected",   "SELECT COUNT(*) FROM bounties"),
        ("Total bounty credits", "SELECT SUM(total_reward) FROM bounties"),
        ("Bodies scanned",       "SELECT COUNT(*) FROM scans"),
        ("Materials collected",  "SELECT COUNT(*) FROM materials_collected"),
        ("Ore refined",          "SELECT COUNT(*) FROM mining_refined"),
        ("Engineer crafts",      "SELECT COUNT(*) FROM engineer_crafts"),
    ]
    with con.cursor() as cur:
        for label, q in queries:
            try:
                cur.execute(q)
                val = cur.fetchone()[0]
                if isinstance(val, float):
                    print(f"  {label:<30} {val:>15,.1f}")
                elif val is not None:
                    print(f"  {label:<30} {val:>15,}")
            except Exception:
                pass


def run_etl(logs_dir: Path, rebuild: bool, verbose: bool):
    # Gather all Journal*.log files (root + subdirs, deduplicated)
    log_files = sorted(set(
        list(logs_dir.glob("Journal*.log")) +
        list(logs_dir.glob("**/Journal*.log"))
    ))
    if not log_files:
        print(f"ERROR: No Journal*.log files found in {logs_dir}", file=sys.stderr)
        sys.exit(1)

    con = connect()
    ensure_processed_logs_table(con)

    if rebuild:
        rebuild_schema(con)
        files_to_process = log_files
        print(f"Rebuild: processing all {len(log_files)} journal files in {logs_dir}")
    else:
        processed = get_processed_files(con)
        files_to_process = [f for f in log_files if f.name not in processed]
        skipped = len(log_files) - len(files_to_process)
        print(f"Found {len(log_files)} journal files in {logs_dir}")
        if skipped:
            print(f"  Skipping {skipped} already-processed file(s)")
        print(f"  Processing {len(files_to_process)} new file(s)")

    if not files_to_process:
        print("Nothing new to load. Run with --rebuild to reload everything.")
        # Still make sure the matview exists on legacy databases that pre-date it
        ensure_jump_aggregates(con)
        _print_quick_stats(con)
        con.close()
        return

    parsed, errors = process_files_list(files_to_process, con, verbose)
    print(f"\nParsed {parsed:,} events ({errors} errors) across {len(files_to_process)} file(s)")

    mark_files_processed(con, [f.name for f in files_to_process], rows_loaded=parsed)

    # Row counts for merged tables
    total = 0
    with con.cursor() as cur:
        for table in ["star_systems", "stations", "commanders"]:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            n = cur.fetchone()[0]
            print(f"  {table:<38} {n:>8,} rows (merged/unique)")
            total += n
    print(f"  Total rows across all tables: {total:,}")

    _print_quick_stats(con)
    con.close()
    print("\nDone.")


# ── CLI ────────────────────────────────────────────────────────

if __name__ == "__main__":
    script_dir = Path(__file__).parent
    parser = argparse.ArgumentParser(description="Elite Dangerous Journal ETL → PostgreSQL")
    parser.add_argument("--logs-dir",
        default=os.environ.get("ED_LOGS_DIR", str(script_dir.parent)),
        help="Folder containing Journal*.log files")
    parser.add_argument("--rebuild", action="store_true",
        help="Drop all tables and reload from scratch")
    parser.add_argument("--verbose", "-v", action="store_true",
        help="Print per-file progress")
    args = parser.parse_args()

    run_etl(
        logs_dir=Path(args.logs_dir),
        rebuild=args.rebuild,
        verbose=args.verbose,
    )
