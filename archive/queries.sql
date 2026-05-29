-- ============================================================
-- Useful DuckDB queries for Elite Dangerous journal data
-- Run from DuckDB CLI: duckdb elite.duckdb
-- ============================================================

-- ── Travel overview ──────────────────────────────────────────
-- Total jumps and distance
SELECT
    COUNT(*)           AS total_jumps,
    ROUND(SUM(jump_dist), 1) AS total_ly,
    ROUND(AVG(jump_dist), 2) AS avg_jump_ly,
    ROUND(MAX(jump_dist), 2) AS max_jump_ly
FROM jumps;

-- Jumps per year
SELECT
    YEAR(timestamp) AS year,
    COUNT(*)        AS jumps,
    ROUND(SUM(jump_dist), 0) AS ly_travelled
FROM jumps
GROUP BY year
ORDER BY year;

-- Most visited star systems
SELECT star_system, visit_count, x, y, z
FROM star_systems
ORDER BY visit_count DESC
LIMIT 20;

-- 3D travel path — all jump coordinates ordered by time (use for 3D map)
SELECT
    timestamp,
    star_system,
    x, y, z,
    jump_dist,
    fuel_used,
    fuel_level
FROM jumps
ORDER BY timestamp;

-- Furthest systems from Sol (0,0,0)
SELECT
    star_system,
    ROUND(SQRT(x*x + y*y + z*z), 1) AS dist_from_sol_ly,
    x, y, z
FROM star_systems
ORDER BY dist_from_sol_ly DESC
LIMIT 20;

-- ── Missions ─────────────────────────────────────────────────
-- Missions accepted vs completed
SELECT
    (SELECT COUNT(*) FROM missions)            AS accepted,
    (SELECT COUNT(*) FROM mission_completions) AS completed;

-- Top earning missions
SELECT
    localised_name,
    destination_system,
    faction,
    FORMAT('{:,}', reward) AS reward_credits
FROM missions
ORDER BY reward DESC
LIMIT 20;

-- Mission types breakdown
SELECT
    REGEXP_REPLACE(name, '_name$', '') AS mission_type,
    COUNT(*)  AS count,
    SUM(reward) AS total_reward
FROM missions
GROUP BY mission_type
ORDER BY count DESC;

-- ── Combat ───────────────────────────────────────────────────
-- Total bounties and earnings
SELECT
    COUNT(*)           AS total_bounties,
    SUM(total_reward)  AS total_credits,
    ROUND(AVG(total_reward), 0) AS avg_reward
FROM bounties;

-- Most hunted ship types
SELECT target_localised, COUNT(*) AS kills
FROM bounties
GROUP BY target_localised
ORDER BY kills DESC;

-- Most bounties collected against a faction
SELECT victim_faction, COUNT(*) AS kills, SUM(total_reward) AS total_reward
FROM bounties
GROUP BY victim_faction
ORDER BY kills DESC
LIMIT 15;

-- ── Exploration ──────────────────────────────────────────────
-- Stars discovered vs already-known
SELECT
    star_type,
    COUNT(*) AS count,
    SUM(CASE WHEN was_discovered = false THEN 1 ELSE 0 END) AS first_discoveries
FROM scans
WHERE star_type IS NOT NULL
GROUP BY star_type
ORDER BY count DESC;

-- Planets by class
SELECT
    planet_class,
    COUNT(*) AS count,
    SUM(CASE WHEN landable = true THEN 1 ELSE 0 END) AS landable
FROM scans
WHERE planet_class IS NOT NULL
GROUP BY planet_class
ORDER BY count DESC;

-- First discoveries only
SELECT body_name, star_system, timestamp
FROM scans
WHERE was_discovered = false
ORDER BY timestamp;

-- ── Engineering ──────────────────────────────────────────────
-- Engineer activity
SELECT engineer, COUNT(*) AS crafts
FROM engineer_crafts
GROUP BY engineer
ORDER BY crafts DESC;

-- Blueprints used
SELECT blueprint_name, COUNT(*) AS times, MAX(level) AS max_level
FROM engineer_crafts
GROUP BY blueprint_name
ORDER BY times DESC;

-- Materials collected by category
SELECT
    category,
    name_localised,
    SUM(count) AS total
FROM materials_collected
GROUP BY category, name_localised
ORDER BY category, total DESC;

-- ── Ships ────────────────────────────────────────────────────
-- Ships flown (by latest loadout)
SELECT DISTINCT ON (ship_ident)
    ship_localised AS ship_type,
    ship_name,
    ship_ident,
    ROUND(max_jump_range, 2) AS jump_range_ly,
    cargo_capacity,
    timestamp AS last_seen
FROM loadouts
JOIN sessions ON loadouts.source_file = sessions.source_file
ORDER BY ship_ident, timestamp DESC;

-- ── Economy ──────────────────────────────────────────────────
-- Credits at each session start over time
SELECT timestamp, commander, FORMAT('{:,}', credits) AS credits
FROM sessions
ORDER BY timestamp;

-- Ore mined by type
SELECT type_localised, COUNT(*) AS units_refined
FROM mining_refined
GROUP BY type_localised
ORDER BY units_refined DESC;

-- ── Stations & factions ──────────────────────────────────────
-- Most visited stations
SELECT station_name, star_system, dock_count
FROM stations
ORDER BY dock_count DESC
LIMIT 20;

-- Systems where you have highest reputation
SELECT system_address, faction_name, my_reputation, timestamp
FROM system_factions
WHERE my_reputation IS NOT NULL
ORDER BY my_reputation DESC
LIMIT 20;
