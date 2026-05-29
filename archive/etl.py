#!/usr/bin/env python3
"""
Elite Dangerous Journal Log ETL
Parses all Journal*.log files and loads them into a DuckDB database.

Usage:
    python etl.py [--logs-dir PATH] [--db-path PATH] [--verbose]

Defaults:
    --logs-dir  ./JournalLogs   (or set ED_LOGS_DIR env var)
    --db-path   ./elite.duckdb  (or set ED_DB_PATH env var)
"""

import argparse
import glob
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_ts(ts_str):
    """Parse ISO timestamp string to datetime, return None on failure."""
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except Exception:
        return None


def row_id(*parts):
    """Stable short hash from concatenated string parts."""
    key = "|".join(str(p) for p in parts)
    return hashlib.md5(key.encode()).hexdigest()[:16]


def clean_localised(value):
    """Strip Frontier's $key_name; localised wrappers, return human text."""
    if not value:
        return value
    if value.startswith("$") and value.endswith(";"):
        return None  # caller should fall back to _Localised field
    return value


# ---------------------------------------------------------------------------
# Per-event parsers — each returns a dict of table -> list[row-dict]
# ---------------------------------------------------------------------------

def parse_fileheader(ev, source_file):
    return {}


def parse_loadgame(ev, source_file):
    ts = parse_ts(ev.get("timestamp"))
    session_id = row_id(source_file, ev.get("timestamp", ""))
    row = {
        "session_id":     session_id,
        "timestamp":      ts,
        "fid":            ev.get("FID"),
        "commander":      ev.get("Commander"),
        "ship":           ev.get("Ship"),
        "ship_localised": ev.get("Ship_Localised"),
        "ship_id":        int(ev.get("ShipID")) if ev.get("ShipID") is not None else None,
        "ship_name":      ev.get("ShipName"),
        "ship_ident":     ev.get("ShipIdent"),
        "fuel_level":     ev.get("FuelLevel"),
        "fuel_capacity":  ev.get("FuelCapacity"),
        "game_mode":      ev.get("GameMode"),
        "game_group":     ev.get("Group"),
        "credits":        ev.get("Credits"),
        "horizons":       ev.get("Horizons"),
        "odyssey":        ev.get("Odyssey"),
        "game_version":   ev.get("gameversion"),
        "source_file":    source_file,
    }
    return {"sessions": [row]}


def parse_commander(ev, source_file):
    ts = parse_ts(ev.get("timestamp"))
    fid = ev.get("FID")
    name = ev.get("Name")
    if not fid:
        return {}
    return {"commanders_raw": [{"fid": fid, "name": name, "timestamp": ts}]}


def parse_rank(ev, source_file):
    ts = parse_ts(ev.get("timestamp"))
    row = {
        "id":           row_id(source_file, ev.get("timestamp", "")),
        "timestamp":    ts,
        "fid":          None,   # filled in post-process if needed
        "combat":       ev.get("Combat"),
        "trade":        ev.get("Trade"),
        "explore":      ev.get("Explore"),
        "soldier":      ev.get("Soldier"),
        "exobiologist": ev.get("Exobiologist"),
        "empire":       ev.get("Empire"),
        "federation":   ev.get("Federation"),
        "cqc":          ev.get("CQC"),
        "source_file":  source_file,
    }
    return {"ranks": [row]}


def _extract_system_row(ev, ts):
    """Pull common star system fields from any event that carries them."""
    pos = ev.get("StarPos", [None, None, None])
    return {
        "system_address": ev.get("SystemAddress"),
        "star_system":    ev.get("StarSystem"),
        "x":              pos[0] if len(pos) > 0 else None,
        "y":              pos[1] if len(pos) > 1 else None,
        "z":              pos[2] if len(pos) > 2 else None,
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


def _extract_factions(ev, ts, source_event, source_id):
    rows = []
    for f in ev.get("Factions", []):
        rows.append({
            "id":           row_id(source_id, f.get("Name", "")),
            "source_event": source_event,
            "source_id":    source_id,
            "system_address": ev.get("SystemAddress"),
            "timestamp":    ts,
            "faction_name": f.get("Name"),
            "faction_state":f.get("FactionState"),
            "government":   f.get("Government"),
            "influence":    f.get("Influence"),
            "allegiance":   f.get("Allegiance"),
            "happiness":    f.get("Happiness_Localised") or f.get("Happiness"),
            "my_reputation":f.get("MyReputation"),
        })
    return rows


def parse_fsdjump(ev, source_file):
    ts = parse_ts(ev.get("timestamp"))
    pos = ev.get("StarPos", [None, None, None])
    jump_id = row_id(ev.get("timestamp", ""), str(ev.get("SystemAddress", "")))

    jump_row = {
        "jump_id":        jump_id,
        "timestamp":      ts,
        "star_system":    ev.get("StarSystem"),
        "system_address": ev.get("SystemAddress"),
        "x":              pos[0] if len(pos) > 0 else None,
        "y":              pos[1] if len(pos) > 1 else None,
        "z":              pos[2] if len(pos) > 2 else None,
        "body":           ev.get("Body"),
        "body_id":        int(ev.get("BodyID")) if ev.get("BodyID") is not None else None,
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
        "source_file":    source_file,
    }

    power_rows = [
        {"jump_id": jump_id, "power": p}
        for p in ev.get("Powers", [])
    ]

    system_row = _extract_system_row(ev, ts)
    faction_rows = _extract_factions(ev, ts, "FSDJump", jump_id)

    return {
        "jumps":           [jump_row],
        "jump_powers":     power_rows,
        "star_systems_raw":[system_row],
        "system_factions": faction_rows,
    }


def parse_location(ev, source_file):
    ts = parse_ts(ev.get("timestamp"))
    pos = ev.get("StarPos", [None, None, None])
    loc_id = row_id(ev.get("timestamp", ""), source_file)

    loc_row = {
        "location_id":    loc_id,
        "timestamp":      ts,
        "star_system":    ev.get("StarSystem"),
        "system_address": ev.get("SystemAddress"),
        "x":              pos[0] if len(pos) > 0 else None,
        "y":              pos[1] if len(pos) > 1 else None,
        "z":              pos[2] if len(pos) > 2 else None,
        "body":           ev.get("Body"),
        "body_id":        int(ev.get("BodyID")) if ev.get("BodyID") is not None else None,
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
        "source_file":    source_file,
    }

    system_row = _extract_system_row(ev, ts)
    faction_rows = _extract_factions(ev, ts, "Location", loc_id)

    return {
        "locations":       [loc_row],
        "star_systems_raw":[system_row],
        "system_factions": faction_rows,
    }


def parse_docked(ev, source_file):
    ts = parse_ts(ev.get("timestamp"))
    dock_id = row_id(ev.get("timestamp", ""), source_file, str(ev.get("MarketID", "")))

    dock_row = {
        "dock_id":        dock_id,
        "timestamp":      ts,
        "station_name":   ev.get("StationName"),
        "station_type":   ev.get("StationType"),
        "star_system":    ev.get("StarSystem"),
        "system_address": ev.get("SystemAddress"),
        "market_id":      ev.get("MarketID"),
        "allegiance":     ev.get("StationAllegiance"),
        "government":     ev.get("StationGovernment_Localised") or ev.get("StationGovernment"),
        "economy":        ev.get("StationEconomy_Localised") or ev.get("StationEconomy"),
        "dist_from_star": ev.get("DistFromStarLS"),
        "active_fine":    ev.get("ActiveFine"),
        "taxi":           ev.get("Taxi"),
        "multicrew":      ev.get("Multicrew"),
        "source_file":    source_file,
    }

    market_id = ev.get("MarketID")
    station_row = None
    if market_id:
        station_row = {
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
        "docked":        [dock_row],
        "stations_raw":  [station_row] if station_row else [],
    }


def parse_missionaccepted(ev, source_file):
    ts = parse_ts(ev.get("timestamp"))
    row = {
        "mission_id":          ev.get("MissionID"),
        "timestamp":           ts,
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
        "source_file":         source_file,
    }
    return {"missions": [row]}


def parse_missioncompleted(ev, source_file):
    ts = parse_ts(ev.get("timestamp"))
    row = {
        "id":                  row_id(ev.get("timestamp", ""), str(ev.get("MissionID", ""))),
        "mission_id":          ev.get("MissionID"),
        "timestamp":           ts,
        "faction":             ev.get("Faction"),
        "name":                ev.get("Name"),
        "kill_count":          ev.get("KillCount"),
        "destination_system":  ev.get("DestinationSystem"),
        "destination_station": ev.get("DestinationStation"),
        "reward":              ev.get("Reward"),
        "source_file":         source_file,
    }
    return {"mission_completions": [row]}


def parse_bounty(ev, source_file):
    ts = parse_ts(ev.get("timestamp"))
    bounty_id = row_id(ev.get("timestamp", ""), source_file, ev.get("Target", ""))
    row = {
        "bounty_id":       bounty_id,
        "timestamp":       ts,
        "target":          ev.get("Target"),
        "target_localised":ev.get("Target_Localised"),
        "total_reward":    ev.get("TotalReward"),
        "victim_faction":  ev.get("VictimFaction"),
        "source_file":     source_file,
    }
    reward_rows = [
        {"bounty_id": bounty_id, "faction": r.get("Faction"), "reward": r.get("Reward")}
        for r in ev.get("Rewards", [])
    ]
    return {"bounties": [row], "bounty_rewards": reward_rows}


def parse_scan(ev, source_file):
    ts = parse_ts(ev.get("timestamp"))
    scan_id = row_id(ev.get("timestamp", ""), str(ev.get("BodyID", "")), source_file)
    row = {
        "scan_id":               scan_id,
        "timestamp":             ts,
        "scan_type":             ev.get("ScanType"),
        "body_name":             ev.get("BodyName"),
        "body_id":               int(ev.get("BodyID")) if ev.get("BodyID") is not None else None,
        "star_system":           ev.get("StarSystem"),
        "system_address":        ev.get("SystemAddress"),
        "distance_from_arrival": ev.get("DistanceFromArrivalLS"),
        "star_type":             ev.get("StarType"),
        "subclass":              int(ev.get("Subclass")) if ev.get("Subclass") is not None else None,
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
        "source_file":           source_file,
    }
    return {"scans": [row]}


def parse_materialcollected(ev, source_file):
    ts = parse_ts(ev.get("timestamp"))
    row = {
        "id":             row_id(ev.get("timestamp", ""), source_file, ev.get("Name", "")),
        "timestamp":      ts,
        "category":       ev.get("Category"),
        "name":           ev.get("Name"),
        "name_localised": ev.get("Name_Localised"),
        "count":          ev.get("Count"),
        "source_file":    source_file,
    }
    return {"materials_collected": [row]}


def parse_miningrefined(ev, source_file):
    ts = parse_ts(ev.get("timestamp"))
    row = {
        "id":             row_id(ev.get("timestamp", ""), source_file),
        "timestamp":      ts,
        "type":           ev.get("Type"),
        "type_localised": ev.get("Type_Localised"),
        "source_file":    source_file,
    }
    return {"mining_refined": [row]}


def parse_engineercraft(ev, source_file):
    ts = parse_ts(ev.get("timestamp"))
    craft_id = row_id(ev.get("timestamp", ""), source_file, ev.get("Slot", ""))
    row = {
        "craft_id":        craft_id,
        "timestamp":       ts,
        "slot":            ev.get("Slot"),
        "module":          ev.get("Module"),
        "engineer":        ev.get("Engineer"),
        "engineer_id":     int(ev.get("EngineerID")) if ev.get("EngineerID") is not None else None,
        "blueprint_id":    ev.get("BlueprintID"),
        "blueprint_name":  ev.get("BlueprintName"),
        "level":           ev.get("Level"),
        "quality":         ev.get("Quality"),
        "experimental_effect": ev.get("ExperimentalEffect"),
        "experimental_effect_localised": ev.get("ExperimentalEffect_Localised"),
        "source_file":     source_file,
    }
    ingredient_rows = [
        {
            "craft_id":      craft_id,
            "name":          i.get("Name"),
            "name_localised":i.get("Name_Localised"),
            "count":         i.get("Count"),
        }
        for i in ev.get("Ingredients", [])
    ]
    modifier_rows = [
        {
            "craft_id":       craft_id,
            "label":          m.get("Label"),
            "value":          m.get("Value"),
            "original_value": m.get("OriginalValue"),
            "less_is_good":   bool(m.get("LessIsGood", 0)),
        }
        for m in ev.get("Modifiers", [])
    ]
    return {
        "engineer_crafts":           [row],
        "engineer_craft_ingredients": ingredient_rows,
        "engineer_craft_modifiers":   modifier_rows,
    }


def parse_loadout(ev, source_file):
    ts = parse_ts(ev.get("timestamp"))
    loadout_id = row_id(ev.get("timestamp", ""), source_file, str(ev.get("ShipID", "")))
    fuel = ev.get("FuelCapacity", {})
    row = {
        "loadout_id":     loadout_id,
        "timestamp":      ts,
        "ship":           ev.get("Ship"),
        "ship_id":        int(ev.get("ShipID")) if ev.get("ShipID") is not None else None,
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
        "source_file":    source_file,
    }
    module_rows = []
    for m in ev.get("Modules", []):
        eng = m.get("Engineering", {}) or {}
        module_rows.append({
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
    return {"loadouts": [row], "ship_modules": module_rows}


def parse_fsssignaldiscovered(ev, source_file):
    ts = parse_ts(ev.get("timestamp"))
    signal_name = ev.get("SignalName", "")
    signal_type = None
    if signal_name.startswith("$") and signal_name.endswith(";"):
        signal_type = ev.get("SignalName_Localised")
    row = {
        "id":                    row_id(ev.get("timestamp", ""), source_file, signal_name),
        "timestamp":             ts,
        "system_address":        ev.get("SystemAddress"),
        "signal_name":           signal_name,
        "signal_name_localised": ev.get("SignalName_Localised"),
        "signal_type":           signal_type,
        "source_file":           source_file,
    }
    return {"fss_signals": [row]}


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Accumulator
# ---------------------------------------------------------------------------

class Accumulator:
    """Collects rows per table, then bulk-inserts with INSERT OR IGNORE."""

    def __init__(self):
        self.tables = {}

    def add(self, results: dict):
        for table, rows in results.items():
            if rows:
                self.tables.setdefault(table, []).extend(rows)

    def total_events(self):
        return sum(len(v) for v in self.tables.values())


# ---------------------------------------------------------------------------
# Database setup & upsert helpers
# ---------------------------------------------------------------------------

SCHEMA_FILE = Path(__file__).parent / "schema.sql"


def init_db(con):
    """Create all tables from schema.sql."""
    sql = SCHEMA_FILE.read_text()
    con.executescript(sql)


def bulk_insert(con, table, rows):
    """Insert a list of dicts into table, ignoring duplicates on PK."""
    if not rows:
        return
    # Filter out None rows
    rows = [r for r in rows if r is not None]
    if not rows:
        return
    cols = list(rows[0].keys())
    placeholders = ", ".join(["?" for _ in cols])
    col_str = ", ".join(cols)
    sql = f"INSERT OR IGNORE INTO {table} ({col_str}) VALUES ({placeholders})"
    values = [[r.get(c) for c in cols] for r in rows]
    con.executemany(sql, values)


def upsert_star_systems(con, rows):
    """Merge star system rows — update coords & visit stats if already present."""
    if not rows:
        return
    rows = [r for r in rows if r and r.get("system_address")]
    if not rows:
        return
    for r in rows:
        existing = con.execute(
            "SELECT system_address, visit_count FROM star_systems WHERE system_address = ?",
            [r["system_address"]]
        ).fetchone()
        if existing:
            con.execute("""
                UPDATE star_systems SET
                    last_visited = GREATEST(last_visited, ?),
                    visit_count  = visit_count + 1,
                    x = COALESCE(x, ?),
                    y = COALESCE(y, ?),
                    z = COALESCE(z, ?)
                WHERE system_address = ?
            """, [r["last_visited"], r["x"], r["y"], r["z"], r["system_address"]])
        else:
            cols = list(r.keys())
            placeholders = ", ".join(["?" for _ in cols])
            col_str = ", ".join(cols)
            con.execute(
                f"INSERT INTO star_systems ({col_str}) VALUES ({placeholders})",
                [r.get(c) for c in cols]
            )


def upsert_stations(con, rows):
    """Merge station rows — update last_docked and dock_count."""
    if not rows:
        return
    rows = [r for r in rows if r and r.get("market_id")]
    if not rows:
        return
    for r in rows:
        existing = con.execute(
            "SELECT market_id FROM stations WHERE market_id = ?",
            [r["market_id"]]
        ).fetchone()
        if existing:
            con.execute("""
                UPDATE stations SET
                    last_docked = GREATEST(last_docked, ?),
                    dock_count  = dock_count + 1
                WHERE market_id = ?
            """, [r["last_docked"], r["market_id"]])
        else:
            cols = list(r.keys())
            placeholders = ", ".join(["?" for _ in cols])
            col_str = ", ".join(cols)
            con.execute(
                f"INSERT INTO stations ({col_str}) VALUES ({placeholders})",
                [r.get(c) for c in cols]
            )


def upsert_commanders(con, rows):
    """Merge commander rows."""
    if not rows:
        return
    for r in rows:
        existing = con.execute(
            "SELECT fid FROM commanders WHERE fid = ?", [r["fid"]]
        ).fetchone()
        if existing:
            con.execute("""
                UPDATE commanders SET
                    last_seen = GREATEST(last_seen, ?)
                WHERE fid = ?
            """, [r["timestamp"], r["fid"]])
        else:
            con.execute(
                "INSERT INTO commanders (fid, name, first_seen, last_seen) VALUES (?, ?, ?, ?)",
                [r["fid"], r["name"], r["timestamp"], r["timestamp"]]
            )


# ---------------------------------------------------------------------------
# Main ETL
# ---------------------------------------------------------------------------

def run_etl(logs_dir: Path, db_path: Path, verbose: bool = False):
    log_files = sorted(logs_dir.glob("Journal*.log"))
    if not log_files:
        print(f"ERROR: No Journal*.log files found in {logs_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(log_files)} journal log files in {logs_dir}")
    print(f"Writing database to {db_path}")

    # CRITICAL: Delete existing database to force schema recreation with correct types
    if db_path.exists():
        db_path.unlink()

    con = duckdb.connect(str(db_path))

    # DuckDB uses standard SQL — no executescript, run each statement
    schema_sql = SCHEMA_FILE.read_text()
    for stmt in schema_sql.split(";"):
        stmt = stmt.strip()
        if stmt:
            try:
                con.execute(stmt)
            except Exception as e:
                if "already exists" not in str(e).lower():
                    print(f"Schema warning: {e}", file=sys.stderr)

    acc = Accumulator()
    skipped = 0
    parsed = 0
    errors = 0

    for fpath in log_files:
        fname = fpath.name
        if verbose:
            print(f"  Parsing {fname} ...", end=" ", flush=True)
        file_parsed = 0
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

                    event_type = ev.get("event", "")
                    parser = EVENT_PARSERS.get(event_type)
                    if parser:
                        try:
                            result = parser(ev, fname)
                            acc.add(result)
                            file_parsed += 1
                        except Exception as e:
                            errors += 1
                            if verbose:
                                print(f"\n    Error in {event_type}: {e}", file=sys.stderr)
                    else:
                        skipped += 1
        except Exception as e:
            print(f"\n  ERROR reading {fname}: {e}", file=sys.stderr)
            continue

        parsed += file_parsed
        if verbose:
            print(f"{file_parsed} events")

    print(f"\nParsed {parsed:,} events across {len(log_files)} files ({errors} errors, {skipped:,} skipped event types)")
    print("Loading into DuckDB...")

    # Insert regular tables
    simple_tables = [
        "sessions", "ranks", "jumps", "jump_powers",
        "locations", "system_factions", "docked",
        "missions", "mission_completions",
        "bounties", "bounty_rewards",
        "scans",
        "materials_collected", "mining_refined",
        "engineer_crafts", "engineer_craft_ingredients", "engineer_craft_modifiers",
        "loadouts", "ship_modules",
        "fss_signals",
    ]

    for table in simple_tables:
        rows = acc.tables.get(table, [])
        if rows:
            bulk_insert(con, table, rows)
            print(f"  {table}: {len(rows):,} rows")

    # Upsert merged tables
    upsert_star_systems(con, acc.tables.get("star_systems_raw", []))
    system_count = con.execute("SELECT COUNT(*) FROM star_systems").fetchone()[0]
    print(f"  star_systems: {system_count:,} unique systems")

    upsert_stations(con, acc.tables.get("stations_raw", []))
    station_count = con.execute("SELECT COUNT(*) FROM stations").fetchone()[0]
    print(f"  stations: {station_count:,} unique stations")

    upsert_commanders(con, acc.tables.get("commanders_raw", []))
    cmd_count = con.execute("SELECT COUNT(*) FROM commanders").fetchone()[0]
    print(f"  commanders: {cmd_count:,} unique commanders")

    con.close()
    print(f"\nDone! Database saved to: {db_path}")

    # Summary stats
    con2 = duckdb.connect(str(db_path), read_only=True)
    print("\n=== Summary ===")
    queries = [
        ("Total jumps",          "SELECT COUNT(*) FROM jumps"),
        ("Unique systems visited","SELECT COUNT(*) FROM star_systems"),
        ("Total ly travelled",   "SELECT ROUND(SUM(jump_dist), 1) FROM jumps"),
        ("Max single jump (ly)", "SELECT ROUND(MAX(jump_dist), 2) FROM jumps"),
        ("Missions accepted",    "SELECT COUNT(*) FROM missions"),
        ("Missions completed",   "SELECT COUNT(*) FROM mission_completions"),
        ("Bounties collected",   "SELECT COUNT(*) FROM bounties"),
        ("Total bounty credits", "SELECT SUM(total_reward) FROM bounties"),
        ("Bodies scanned",       "SELECT COUNT(*) FROM scans"),
        ("Materials collected",  "SELECT COUNT(*) FROM materials_collected"),
        ("Engineer crafts",      "SELECT COUNT(*) FROM engineer_crafts"),
        ("Ore refined",          "SELECT COUNT(*) FROM mining_refined"),
        ("Play sessions",        "SELECT COUNT(*) FROM sessions"),
        ("Ships tracked",        "SELECT COUNT(DISTINCT ship_ident) FROM loadouts WHERE ship_ident IS NOT NULL"),
    ]
    for label, q in queries:
        try:
            val = con2.execute(q).fetchone()[0]
            if val is not None and isinstance(val, float):
                val = f"{val:,.1f}"
            elif val is not None:
                val = f"{val:,}"
            print(f"  {label:<28} {val}")
        except Exception:
            pass
    con2.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Elite Dangerous Journal Log ETL → DuckDB")
    parser.add_argument(
        "--logs-dir",
        default=os.environ.get("ED_LOGS_DIR", "./JournalLogs"),
        help="Directory containing Journal*.log files"
    )
    parser.add_argument(
        "--db-path",
        default=os.environ.get("ED_DB_PATH", "./elite.duckdb"),
        help="Output DuckDB database file path"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Print per-file progress")
    args = parser.parse_args()

    run_etl(
        logs_dir=Path(args.logs_dir),
        db_path=Path(args.db_path),
        verbose=args.verbose,
    )
