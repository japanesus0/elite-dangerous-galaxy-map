"""Unit tests for the per-event parsers in etl.py.

These tests are fast and DB-free — they exercise only the pure-python parsing
layer. Sample events are trimmed copies of real Frontier journal entries.
"""

from __future__ import annotations

from datetime import datetime, timezone

import etl


# ── helpers ────────────────────────────────────────────────────────

def _ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


# ── parse_ts / row_id ──────────────────────────────────────────────

def test_parse_ts_handles_iso_z():
    assert etl.parse_ts("2025-06-09T23:23:03Z") == _ts("2025-06-09T23:23:03Z")


def test_parse_ts_handles_offsets():
    assert etl.parse_ts("2025-06-09T23:23:03+00:00") == _ts("2025-06-09T23:23:03Z")


def test_parse_ts_returns_none_on_garbage():
    assert etl.parse_ts(None) is None
    assert etl.parse_ts("") is None
    assert etl.parse_ts("not a date") is None


def test_row_id_is_deterministic_and_short():
    a = etl.row_id("foo", "bar", 42)
    b = etl.row_id("foo", "bar", 42)
    c = etl.row_id("foo", "bar", 43)
    assert a == b
    assert a != c
    assert len(a) == 16


# ── FSDJump (the main travel event) ────────────────────────────────

FSDJUMP_EVENT = {
    "timestamp": "2025-06-09T23:23:03Z",
    "event": "FSDJump",
    "Taxi": False,
    "Multicrew": False,
    "StarSystem": "Alrai Sector QT-R b4-8",
    "SystemAddress": 18262066800081,
    "StarPos": [-77.5625, 1.6875, 96.25],
    "SystemAllegiance": "Independent",
    "SystemEconomy": "$economy_Industrial;",
    "SystemEconomy_Localised": "Industrial",
    "SystemGovernment": "$government_Corporate;",
    "SystemGovernment_Localised": "Corporate",
    "SystemSecurity": "$SYSTEM_SECURITY_low;",
    "SystemSecurity_Localised": "Low Security",
    "Population": 60857,
    "Body": "Alrai Sector QT-R b4-8 A",
    "BodyID": 1,
    "BodyType": "Star",
    "JumpDist": 16.139,
    "FuelUsed": 2.947399,
    "FuelLevel": 29.052601,
    "Powers": ["Archon Delaine", "Pranav Antal"],
    "PowerplayState": "Unoccupied",
    "Factions": [
        {"Name": "Orange society",   "FactionState": "None",
         "Government": "Corporate",  "Influence": 0.5, "Allegiance": "Independent",
         "Happiness_Localised": "Happy", "MyReputation": 0.0},
        {"Name": "Tembala Systems",  "FactionState": "None",
         "Government": "Corporate",  "Influence": 0.2, "Allegiance": "Independent",
         "Happiness_Localised": "Happy", "MyReputation": -5.0},
    ],
}


def test_parse_fsdjump_populates_jump_row():
    out = etl.parse_fsdjump(FSDJUMP_EVENT, "Journal.test.log")

    assert "jumps" in out and len(out["jumps"]) == 1
    j = out["jumps"][0]

    assert j["star_system"] == "Alrai Sector QT-R b4-8"
    assert j["system_address"] == 18262066800081
    assert (j["x"], j["y"], j["z"]) == (-77.5625, 1.6875, 96.25)
    assert j["jump_dist"] == 16.139
    # Localised values should win over the symbol form
    assert j["economy"] == "Industrial"
    assert j["government"] == "Corporate"
    assert j["security"] == "Low Security"
    assert j["source_file"] == "Journal.test.log"
    assert j["timestamp"] == _ts("2025-06-09T23:23:03Z")


def test_parse_fsdjump_jump_id_is_deterministic():
    a = etl.parse_fsdjump(FSDJUMP_EVENT, "f.log")["jumps"][0]["jump_id"]
    b = etl.parse_fsdjump(FSDJUMP_EVENT, "f.log")["jumps"][0]["jump_id"]
    assert a == b


def test_parse_fsdjump_jump_powers_link_back():
    out = etl.parse_fsdjump(FSDJUMP_EVENT, "f.log")
    jump_id = out["jumps"][0]["jump_id"]
    assert {p["power"] for p in out["jump_powers"]} == {"Archon Delaine", "Pranav Antal"}
    assert all(p["jump_id"] == jump_id for p in out["jump_powers"])


def test_parse_fsdjump_emits_star_system_row():
    out = etl.parse_fsdjump(FSDJUMP_EVENT, "f.log")
    sys_row = out["star_systems_raw"][0]
    assert sys_row["system_address"] == 18262066800081
    assert sys_row["visit_count"] == 1
    assert sys_row["first_visited"] == sys_row["last_visited"]


def test_parse_fsdjump_factions_get_unique_ids():
    out = etl.parse_fsdjump(FSDJUMP_EVENT, "f.log")
    ids = [f["id"] for f in out["system_factions"]]
    assert len(ids) == 2
    assert len(set(ids)) == 2  # unique per faction


def test_faction_id_does_not_collide_across_events():
    """Regression — same faction reported by FSDJump and Location at the same
    moment used to collide because the row id only mixed source_id+name."""
    same_event = dict(FSDJUMP_EVENT)
    fsd  = etl.parse_fsdjump(same_event,   "f.log")["system_factions"][0]["id"]
    # Build a Location event at the same timestamp/system to provoke the
    # historical collision case.
    loc_ev = dict(same_event); loc_ev["event"] = "Location"
    loc_ev.setdefault("Docked", False)
    loc  = etl.parse_location(loc_ev, "f.log")["system_factions"][0]["id"]
    assert fsd != loc, "FSDJump and Location factions must get distinct ids"


# ── Scan (the heaviest schema) ─────────────────────────────────────

SCAN_PLANET = {
    "timestamp": "2025-06-09T23:24:10Z",
    "event": "Scan",
    "ScanType": "AutoScan",
    "BodyName": "Alrai Sector QT-R b4-8 A 1",
    "BodyID": 5,
    "StarSystem": "Alrai Sector QT-R b4-8",
    "SystemAddress": 18262066800081,
    "DistanceFromArrivalLS": 482.32,
    "PlanetClass": "Earthlike body",
    "MassEM": 0.83,
    "Landable": False,
    "Atmosphere": "earthlike atmosphere",
    "SurfaceGravity": 9.21,
    "TidalLock": True,
    "WasDiscovered": False,
    "WasMapped": False,
}


def test_parse_scan_handles_planet():
    out = etl.parse_scan(SCAN_PLANET, "f.log")
    s = out["scans"][0]
    assert s["body_name"] == "Alrai Sector QT-R b4-8 A 1"
    assert s["planet_class"] == "Earthlike body"
    assert s["landable"] is False
    assert s["was_discovered"] is False
    assert s["star_type"] is None  # not a star


SCAN_STAR = {
    "timestamp": "2025-06-09T23:24:10Z",
    "event": "Scan",
    "BodyName": "Alrai Sector QT-R b4-8 A",
    "BodyID": 1,
    "StarType": "M",
    "Subclass": 5,
    "StellarMass": 0.42,
    "Radius": 320000.0,
    "Luminosity": "Va",
    "Age_MY": 5840,
    "WasDiscovered": True,
}


def test_parse_scan_handles_star():
    s = etl.parse_scan(SCAN_STAR, "f.log")["scans"][0]
    assert s["star_type"] == "M"
    assert s["luminosity"] == "Va"
    assert s["was_discovered"] is True
    assert s["planet_class"] is None


# ── Bounty (with reward sub-rows) ──────────────────────────────────

BOUNTY_EVENT = {
    "timestamp": "2025-06-09T23:30:00Z",
    "event": "Bounty",
    "Target": "asp",
    "Target_Localised": "Asp Explorer",
    "TotalReward": 50000,
    "VictimFaction": "Pirates of LTT 15587",
    "Rewards": [
        {"Faction": "Federation", "Reward": 30000},
        {"Faction": "Independent", "Reward": 20000},
    ],
}


def test_parse_bounty_emits_rewards_keyed_by_bounty_id():
    out = etl.parse_bounty(BOUNTY_EVENT, "f.log")
    bid = out["bounties"][0]["bounty_id"]
    rewards = out["bounty_rewards"]
    assert {r["faction"] for r in rewards} == {"Federation", "Independent"}
    assert all(r["bounty_id"] == bid for r in rewards)
    assert sum(r["reward"] for r in rewards) == 50000


# ── FSSSignalDiscovered (regression for the SignalType bug) ────────

def test_parse_fss_signal_uses_explicit_signal_type_when_present():
    ev = {
        "timestamp": "2025-06-09T23:35:00Z",
        "event": "FSSSignalDiscovered",
        "SignalName": "$MULTIPLAYER_SCENARIO80_TITLE;",
        "SignalName_Localised": "Nav Beacon",
        "SignalType": "NavBeacon",
        "SystemAddress": 18262066800081,
    }
    s = etl.parse_fsssignaldiscovered(ev, "f.log")["fss_signals"][0]
    assert s["signal_type"] == "NavBeacon"


def test_parse_fss_signal_falls_back_to_localised_for_symbol_names():
    ev = {
        "timestamp": "2025-06-09T23:35:00Z",
        "event": "FSSSignalDiscovered",
        "SignalName": "$Warzone_PointRace_High;",
        "SignalName_Localised": "High-Intensity Conflict Zone",
        "SystemAddress": 18262066800081,
    }
    s = etl.parse_fsssignaldiscovered(ev, "f.log")["fss_signals"][0]
    assert s["signal_type"] == "High-Intensity Conflict Zone"


def test_parse_fss_signal_leaves_type_null_for_named_signals():
    """Named USS / installation signals without a SignalType should not
    invent one from the localised text."""
    ev = {
        "timestamp": "2025-06-09T23:35:00Z",
        "event": "FSSSignalDiscovered",
        "SignalName": "PRIVATE INSTALLATION 7H-X9F",
        "SystemAddress": 18262066800081,
    }
    s = etl.parse_fsssignaldiscovered(ev, "f.log")["fss_signals"][0]
    assert s["signal_type"] is None


# ── LoadGame (session) ─────────────────────────────────────────────

def test_parse_loadgame_builds_session():
    ev = {
        "timestamp": "2025-06-09T23:00:00Z",
        "event": "LoadGame",
        "FID": "F1234567",
        "Commander": "Karr",
        "Ship": "anaconda",
        "Ship_Localised": "Anaconda",
        "ShipID": 7,
        "ShipName": "Stellar Wind",
        "ShipIdent": "KR-01",
        "FuelLevel": 28.5,
        "FuelCapacity": 32.0,
        "GameMode": "Solo",
        "Credits": 1234567890,
        "Horizons": True,
        "Odyssey": True,
        "gameversion": "4.1.0.0",
    }
    s = etl.parse_loadgame(ev, "f.log")["sessions"][0]
    assert s["fid"] == "F1234567"
    assert s["commander"] == "Karr"
    assert s["ship"] == "anaconda"
    assert s["ship_localised"] == "Anaconda"
    assert s["fuel_capacity"] == 32.0
    assert s["odyssey"] is True


# ── Loadout (modules sub-rows) ─────────────────────────────────────

def test_parse_loadout_extracts_engineered_module_blueprint():
    ev = {
        "timestamp": "2025-06-09T23:01:00Z",
        "event": "Loadout",
        "Ship": "anaconda",
        "ShipID": 7,
        "ShipName": "Stellar Wind",
        "ShipIdent": "KR-01",
        "HullValue": 100000000,
        "ModulesValue": 250000000,
        "HullHealth": 1.0,
        "UnladenMass": 400.0,
        "CargoCapacity": 64,
        "MaxJumpRange": 47.2,
        "FuelCapacity": {"Main": 32.0, "Reserve": 1.07},
        "Rebuy": 17500000,
        "Modules": [
            {
                "Slot": "FrameShiftDrive",
                "Item": "int_hyperdrive_size7_class5",
                "On": True, "Priority": 0, "Health": 1.0, "Value": 5103950,
                "Engineering": {
                    "Engineer": "Felicity Farseer",
                    "BlueprintName": "FSD_LongRange",
                    "Level": 5, "Quality": 1.0,
                    "ExperimentalEffect": "special_fsd_heavy",
                },
            },
        ],
    }
    out = etl.parse_loadout(ev, "f.log")
    ld = out["loadouts"][0]
    assert ld["ship"] == "anaconda"
    assert ld["fuel_main"] == 32.0
    assert ld["fuel_reserve"] == 1.07
    assert ld["max_jump_range"] == 47.2

    mods = out["ship_modules"]
    assert len(mods) == 1
    m = mods[0]
    assert m["slot"] == "FrameShiftDrive"
    assert m["engineer"] == "Felicity Farseer"
    assert m["blueprint_name"] == "FSD_LongRange"
    assert m["blueprint_level"] == 5


# ── EngineerCraft (ingredients + modifiers) ────────────────────────

def test_parse_engineer_craft_links_children_to_craft_id():
    ev = {
        "timestamp": "2025-06-10T00:00:00Z",
        "event": "EngineerCraft",
        "Slot": "PowerDistributor",
        "Module": "int_powerdistributor_size7_class5",
        "Engineer": "The Dweller",
        "EngineerID": 300180,
        "BlueprintID": 128673765,
        "BlueprintName": "PowerDistributor_HighFrequency",
        "Level": 5, "Quality": 1.0,
        "Ingredients": [
            {"Name": "chemicalmanipulators", "Name_Localised": "Chemical Manipulators", "Count": 1},
        ],
        "Modifiers": [
            {"Label": "WeaponsCapacity", "Value": 51.0, "OriginalValue": 41.0, "LessIsGood": 0},
        ],
    }
    out = etl.parse_engineercraft(ev, "f.log")
    cid = out["engineer_crafts"][0]["craft_id"]
    assert all(i["craft_id"] == cid for i in out["engineer_craft_ingredients"])
    assert all(m["craft_id"] == cid for m in out["engineer_craft_modifiers"])
    assert out["engineer_craft_modifiers"][0]["less_is_good"] is False
