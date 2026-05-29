-- ============================================================
-- Elite Dangerous Journal Logs — PostgreSQL Schema
-- Applied automatically on first `docker compose up` via
-- /docker-entrypoint-initdb.d/ — do not run manually.
-- To rebuild: docker compose run --rm elite-etl --rebuild
-- ============================================================

CREATE TABLE IF NOT EXISTS sessions (
    session_id       TEXT PRIMARY KEY,
    timestamp        TIMESTAMPTZ NOT NULL,
    fid              TEXT,
    commander        TEXT,
    ship             TEXT,
    ship_localised   TEXT,
    ship_id          BIGINT,
    ship_name        TEXT,
    ship_ident       TEXT,
    fuel_level       DOUBLE PRECISION,
    fuel_capacity    DOUBLE PRECISION,
    game_mode        TEXT,
    game_group       TEXT,
    credits          BIGINT,
    horizons         BOOLEAN,
    odyssey          BOOLEAN,
    game_version     TEXT,
    source_file      TEXT
);

CREATE TABLE IF NOT EXISTS commanders (
    fid              TEXT PRIMARY KEY,
    name             TEXT,
    first_seen       TIMESTAMPTZ,
    last_seen        TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS ranks (
    id               TEXT PRIMARY KEY,
    timestamp        TIMESTAMPTZ NOT NULL,
    fid              TEXT,
    combat           BIGINT,
    trade            BIGINT,
    explore          BIGINT,
    soldier          BIGINT,
    exobiologist     BIGINT,
    empire           BIGINT,
    federation       BIGINT,
    cqc              BIGINT,
    source_file      TEXT
);

-- Core travel table — drives the 3D map
CREATE TABLE IF NOT EXISTS jumps (
    jump_id          TEXT PRIMARY KEY,
    timestamp        TIMESTAMPTZ NOT NULL,
    star_system      TEXT NOT NULL,
    system_address   BIGINT,
    x                DOUBLE PRECISION,
    y                DOUBLE PRECISION,
    z                DOUBLE PRECISION,
    body             TEXT,
    body_id          BIGINT,
    body_type        TEXT,
    jump_dist        DOUBLE PRECISION,
    fuel_used        DOUBLE PRECISION,
    fuel_level       DOUBLE PRECISION,
    allegiance       TEXT,
    economy          TEXT,
    government       TEXT,
    security         TEXT,
    population       BIGINT,
    powerplay_state  TEXT,
    taxi             BOOLEAN,
    multicrew        BOOLEAN,
    source_file      TEXT
);

CREATE TABLE IF NOT EXISTS jump_powers (
    jump_id          TEXT,
    power            TEXT,
    PRIMARY KEY (jump_id, power)
);

CREATE TABLE IF NOT EXISTS star_systems (
    system_address   BIGINT PRIMARY KEY,
    star_system      TEXT NOT NULL,
    x                DOUBLE PRECISION,
    y                DOUBLE PRECISION,
    z                DOUBLE PRECISION,
    allegiance       TEXT,
    economy          TEXT,
    second_economy   TEXT,
    government       TEXT,
    security         TEXT,
    population       BIGINT,
    first_visited    TIMESTAMPTZ,
    last_visited     TIMESTAMPTZ,
    visit_count      BIGINT DEFAULT 1
);

CREATE TABLE IF NOT EXISTS locations (
    location_id      TEXT PRIMARY KEY,
    timestamp        TIMESTAMPTZ NOT NULL,
    star_system      TEXT,
    system_address   BIGINT,
    x                DOUBLE PRECISION,
    y                DOUBLE PRECISION,
    z                DOUBLE PRECISION,
    body             TEXT,
    body_id          BIGINT,
    body_type        TEXT,
    docked           BOOLEAN,
    station_name     TEXT,
    station_type     TEXT,
    market_id        BIGINT,
    dist_from_star   DOUBLE PRECISION,
    allegiance       TEXT,
    economy          TEXT,
    government       TEXT,
    security         TEXT,
    population       BIGINT,
    source_file      TEXT
);

CREATE TABLE IF NOT EXISTS system_factions (
    id               TEXT PRIMARY KEY,
    source_event     TEXT,
    source_id        TEXT,
    system_address   BIGINT,
    timestamp        TIMESTAMPTZ,
    faction_name     TEXT,
    faction_state    TEXT,
    government       TEXT,
    influence        DOUBLE PRECISION,
    allegiance       TEXT,
    happiness        TEXT,
    my_reputation    DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS stations (
    market_id        BIGINT PRIMARY KEY,
    station_name     TEXT,
    station_type     TEXT,
    star_system      TEXT,
    system_address   BIGINT,
    allegiance       TEXT,
    government       TEXT,
    economy          TEXT,
    dist_from_star   DOUBLE PRECISION,
    first_docked     TIMESTAMPTZ,
    last_docked      TIMESTAMPTZ,
    dock_count       BIGINT DEFAULT 1
);

CREATE TABLE IF NOT EXISTS docked (
    dock_id          TEXT PRIMARY KEY,
    timestamp        TIMESTAMPTZ NOT NULL,
    station_name     TEXT,
    station_type     TEXT,
    star_system      TEXT,
    system_address   BIGINT,
    market_id        BIGINT,
    allegiance       TEXT,
    government       TEXT,
    economy          TEXT,
    dist_from_star   DOUBLE PRECISION,
    active_fine      BOOLEAN,
    taxi             BOOLEAN,
    multicrew        BOOLEAN,
    source_file      TEXT
);

CREATE TABLE IF NOT EXISTS missions (
    mission_id          BIGINT PRIMARY KEY,
    timestamp           TIMESTAMPTZ NOT NULL,
    faction             TEXT,
    name                TEXT,
    localised_name      TEXT,
    target_type         TEXT,
    target_faction      TEXT,
    kill_count          BIGINT,
    destination_system  TEXT,
    destination_station TEXT,
    expiry              TIMESTAMPTZ,
    wing                BOOLEAN,
    influence           TEXT,
    reputation          TEXT,
    reward              BIGINT,
    source_file         TEXT
);

CREATE TABLE IF NOT EXISTS mission_completions (
    id                  TEXT PRIMARY KEY,
    mission_id          BIGINT,
    timestamp           TIMESTAMPTZ NOT NULL,
    faction             TEXT,
    name                TEXT,
    kill_count          BIGINT,
    destination_system  TEXT,
    destination_station TEXT,
    reward              BIGINT,
    source_file         TEXT
);

CREATE TABLE IF NOT EXISTS bounties (
    bounty_id        TEXT PRIMARY KEY,
    timestamp        TIMESTAMPTZ NOT NULL,
    target           TEXT,
    target_localised TEXT,
    total_reward     BIGINT,
    victim_faction   TEXT,
    source_file      TEXT
);

CREATE TABLE IF NOT EXISTS bounty_rewards (
    bounty_id        TEXT,
    faction          TEXT,
    reward           BIGINT,
    PRIMARY KEY (bounty_id, faction)
);

CREATE TABLE IF NOT EXISTS scans (
    scan_id               TEXT PRIMARY KEY,
    timestamp             TIMESTAMPTZ NOT NULL,
    scan_type             TEXT,
    body_name             TEXT,
    body_id               BIGINT,
    star_system           TEXT,
    system_address        BIGINT,
    distance_from_arrival DOUBLE PRECISION,
    -- Star fields
    star_type             TEXT,
    subclass              BIGINT,
    stellar_mass          DOUBLE PRECISION,
    radius                DOUBLE PRECISION,
    surface_temp          DOUBLE PRECISION,
    luminosity            TEXT,
    age_my                BIGINT,
    -- Planet/moon fields
    planet_class          TEXT,
    mass_em               DOUBLE PRECISION,
    landable              BOOLEAN,
    atmosphere            TEXT,
    volcanism             TEXT,
    surface_gravity       DOUBLE PRECISION,
    surface_pressure      DOUBLE PRECISION,
    tidal_lock            BOOLEAN,
    -- Orbital elements
    semi_major_axis       DOUBLE PRECISION,
    eccentricity          DOUBLE PRECISION,
    orbital_incl          DOUBLE PRECISION,
    orbital_period        DOUBLE PRECISION,
    rotation_period       DOUBLE PRECISION,
    axial_tilt            DOUBLE PRECISION,
    -- Discovery flags
    was_discovered        BOOLEAN,
    was_mapped            BOOLEAN,
    source_file           TEXT
);

CREATE TABLE IF NOT EXISTS materials_collected (
    id               TEXT PRIMARY KEY,
    timestamp        TIMESTAMPTZ NOT NULL,
    category         TEXT,
    name             TEXT,
    name_localised   TEXT,
    count            BIGINT,
    source_file      TEXT
);

CREATE TABLE IF NOT EXISTS mining_refined (
    id               TEXT PRIMARY KEY,
    timestamp        TIMESTAMPTZ NOT NULL,
    type             TEXT,
    type_localised   TEXT,
    source_file      TEXT
);

CREATE TABLE IF NOT EXISTS engineer_crafts (
    craft_id                      TEXT PRIMARY KEY,
    timestamp                     TIMESTAMPTZ NOT NULL,
    slot                          TEXT,
    module                        TEXT,
    engineer                      TEXT,
    engineer_id                   BIGINT,
    blueprint_id                  BIGINT,
    blueprint_name                TEXT,
    level                         BIGINT,
    quality                       DOUBLE PRECISION,
    experimental_effect           TEXT,
    experimental_effect_localised TEXT,
    source_file                   TEXT
);

CREATE TABLE IF NOT EXISTS engineer_craft_ingredients (
    craft_id         TEXT,
    name             TEXT,
    name_localised   TEXT,
    count            BIGINT,
    PRIMARY KEY (craft_id, name)
);

CREATE TABLE IF NOT EXISTS engineer_craft_modifiers (
    craft_id         TEXT,
    label            TEXT,
    value            DOUBLE PRECISION,
    original_value   DOUBLE PRECISION,
    less_is_good     BOOLEAN,
    PRIMARY KEY (craft_id, label)
);

CREATE TABLE IF NOT EXISTS loadouts (
    loadout_id       TEXT PRIMARY KEY,
    timestamp        TIMESTAMPTZ NOT NULL,
    ship             TEXT,
    ship_id          BIGINT,
    ship_name        TEXT,
    ship_ident       TEXT,
    hull_value       BIGINT,
    modules_value    BIGINT,
    hull_health      DOUBLE PRECISION,
    unladen_mass     DOUBLE PRECISION,
    cargo_capacity   BIGINT,
    max_jump_range   DOUBLE PRECISION,
    fuel_main        DOUBLE PRECISION,
    fuel_reserve     DOUBLE PRECISION,
    rebuy            BIGINT,
    source_file      TEXT
);

CREATE TABLE IF NOT EXISTS ship_modules (
    loadout_id          TEXT,
    slot                TEXT,
    item                TEXT,
    is_on               BOOLEAN,
    priority            BIGINT,
    health              DOUBLE PRECISION,
    value               BIGINT,
    engineer            TEXT,
    blueprint_name      TEXT,
    blueprint_level     BIGINT,
    blueprint_quality   DOUBLE PRECISION,
    experimental_effect TEXT,
    PRIMARY KEY (loadout_id, slot)
);

CREATE TABLE IF NOT EXISTS fss_signals (
    id                    TEXT PRIMARY KEY,
    timestamp             TIMESTAMPTZ NOT NULL,
    system_address        BIGINT,
    signal_name           TEXT,
    signal_name_localised TEXT,
    signal_type           TEXT,
    source_file           TEXT
);

-- Indexes for the most common join patterns in the map query
CREATE INDEX IF NOT EXISTS idx_jumps_timestamp        ON jumps (timestamp);
CREATE INDEX IF NOT EXISTS idx_jumps_system_address   ON jumps (system_address);
CREATE INDEX IF NOT EXISTS idx_jumps_source_file      ON jumps (source_file);
CREATE INDEX IF NOT EXISTS idx_scans_system_address   ON scans (system_address);
CREATE INDEX IF NOT EXISTS idx_scans_timestamp        ON scans (timestamp);
CREATE INDEX IF NOT EXISTS idx_bounties_timestamp     ON bounties (timestamp);
CREATE INDEX IF NOT EXISTS idx_materials_timestamp    ON materials_collected (timestamp);
CREATE INDEX IF NOT EXISTS idx_missions_timestamp     ON missions (timestamp);
CREATE INDEX IF NOT EXISTS idx_sessions_timestamp     ON sessions (timestamp);
CREATE INDEX IF NOT EXISTS idx_sessions_source_file   ON sessions (source_file);
CREATE INDEX IF NOT EXISTS idx_mining_timestamp       ON mining_refined (timestamp);
CREATE INDEX IF NOT EXISTS idx_star_systems_address   ON star_systems (system_address);

-- ============================================================
-- jump_aggregates — precomputed per-jump summary
-- ------------------------------------------------------------
-- The /api/jumps endpoint used to compute this on every request via a
-- 7-CTE join over the entire jumps table. Materialising it once and
-- refreshing after each ETL load collapses /api/jumps to a single
-- indexed scan.
--
-- Refreshed by etl.refresh_jump_aggregates() at the end of every run.
-- ============================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS jump_aggregates AS
WITH jw AS (
    SELECT
        jump_id,
        source_file,
        star_system,
        system_address,
        timestamp                                          AS jump_time,
        LEAD(timestamp) OVER (ORDER BY timestamp)          AS next_time,
        x, y, z,
        ROUND(jump_dist::numeric, 2)                       AS jump_dist,
        security,
        population
    FROM jumps
)
SELECT
    jw.jump_id,
    jw.source_file,
    jw.jump_time,
    jw.star_system,
    jw.system_address,
    jw.x, jw.y, jw.z,
    jw.jump_dist,
    jw.security,
    jw.population,
    COALESCE(disc.disc_count,     0) AS first_discoveries,
    disc.disc_bodies,
    COALESCE(el.el_count,         0) AS earth_likes,
    el.el_bodies,
    COALESCE(combat.bounty_count, 0) AS bounties_collected,
    COALESCE(combat.credits,      0) AS bounty_credits,
    COALESCE(mats.mat_count,      0) AS materials_collected,
    COALESCE(miss.mission_count,  0) AS missions,
    COALESCE(sess.session_count,  0) AS sessions,
    COALESCE(mining.mined_count,  0) AS minerals_mined
FROM jw
LEFT JOIN LATERAL (
    SELECT COUNT(*) AS disc_count,
           STRING_AGG(s.body_name, ' | ' ORDER BY s.timestamp) AS disc_bodies
    FROM   scans s
    WHERE  s.system_address = jw.system_address
      AND  s.timestamp >= jw.jump_time
      AND  (s.timestamp < jw.next_time OR jw.next_time IS NULL)
      AND  s.was_discovered = true
) disc ON true
LEFT JOIN LATERAL (
    SELECT COUNT(*) AS el_count,
           STRING_AGG(s.body_name, ' | ' ORDER BY s.timestamp) AS el_bodies
    FROM   scans s
    WHERE  s.system_address = jw.system_address
      AND  s.timestamp >= jw.jump_time
      AND  (s.timestamp < jw.next_time OR jw.next_time IS NULL)
      AND  s.planet_class ILIKE 'Earthlike%'
) el ON true
LEFT JOIN LATERAL (
    SELECT COUNT(*) AS bounty_count,
           COALESCE(SUM(b.total_reward), 0) AS credits
    FROM   bounties b
    WHERE  b.timestamp >= jw.jump_time
      AND  (b.timestamp < jw.next_time OR jw.next_time IS NULL)
) combat ON true
LEFT JOIN LATERAL (
    SELECT COALESCE(SUM(mc.count), 0) AS mat_count
    FROM   materials_collected mc
    WHERE  mc.timestamp >= jw.jump_time
      AND  (mc.timestamp < jw.next_time OR jw.next_time IS NULL)
) mats ON true
LEFT JOIN LATERAL (
    SELECT COUNT(*) AS mission_count
    FROM   missions m
    WHERE  m.timestamp >= jw.jump_time
      AND  (m.timestamp < jw.next_time OR jw.next_time IS NULL)
) miss ON true
LEFT JOIN LATERAL (
    SELECT COUNT(*) AS session_count
    FROM   sessions s2
    WHERE  s2.timestamp >= jw.jump_time
      AND  (s2.timestamp < jw.next_time OR jw.next_time IS NULL)
) sess ON true
LEFT JOIN LATERAL (
    SELECT COUNT(*) AS mined_count
    FROM   mining_refined mr
    WHERE  mr.timestamp >= jw.jump_time
      AND  (mr.timestamp < jw.next_time OR jw.next_time IS NULL)
) mining ON true
WHERE jw.x IS NOT NULL AND jw.y IS NOT NULL AND jw.z IS NOT NULL;

-- Unique index required for REFRESH MATERIALIZED VIEW CONCURRENTLY,
-- and serves as the primary lookup for /api/jumps ordering.
CREATE UNIQUE INDEX IF NOT EXISTS idx_jump_aggregates_jump_id
    ON jump_aggregates (jump_id);
CREATE INDEX IF NOT EXISTS idx_jump_aggregates_jump_time
    ON jump_aggregates (jump_time);
CREATE INDEX IF NOT EXISTS idx_jump_aggregates_source_file
    ON jump_aggregates (source_file);
