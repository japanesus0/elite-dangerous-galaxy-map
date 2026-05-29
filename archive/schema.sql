-- ============================================================
-- Elite Dangerous Journal Logs — DuckDB Schema
-- ============================================================

-- Sessions (one per LoadGame event)
CREATE TABLE IF NOT EXISTS sessions (
    session_id       VARCHAR PRIMARY KEY,   -- source_file + timestamp
    timestamp        TIMESTAMPTZ NOT NULL,
    fid              VARCHAR,               -- Frontier commander ID
    commander        VARCHAR,
    ship             VARCHAR,
    ship_localised   VARCHAR,
    ship_id          BIGINT,
    ship_name        VARCHAR,
    ship_ident       VARCHAR,
    fuel_level       DOUBLE,
    fuel_capacity    DOUBLE,
    game_mode        VARCHAR,
    game_group       VARCHAR,
    credits          BIGINT,
    horizons         BOOLEAN,
    odyssey          BOOLEAN,
    game_version     VARCHAR,
    source_file      VARCHAR
);

-- Commanders (unique FID snapshots)
CREATE TABLE IF NOT EXISTS commanders (
    fid              VARCHAR PRIMARY KEY,
    name             VARCHAR,
    first_seen       TIMESTAMPTZ,
    last_seen        TIMESTAMPTZ
);

-- Ranks (snapshot per session load)
CREATE TABLE IF NOT EXISTS ranks (
    id               VARCHAR PRIMARY KEY,
    timestamp        TIMESTAMPTZ NOT NULL,
    fid              VARCHAR,
    combat           INTEGER,
    trade            INTEGER,
    explore          INTEGER,
    soldier          INTEGER,
    exobiologist     INTEGER,
    empire           INTEGER,
    federation       INTEGER,
    cqc              INTEGER,
    source_file      VARCHAR
);

-- Star Systems (deduplicated by SystemAddress)
CREATE TABLE IF NOT EXISTS star_systems (
    system_address   BIGINT PRIMARY KEY,
    star_system      VARCHAR NOT NULL,
    x                DOUBLE,              -- Galactic X coord (ly)
    y                DOUBLE,              -- Galactic Y coord (ly)
    z                DOUBLE,              -- Galactic Z coord (ly)
    allegiance       VARCHAR,
    economy          VARCHAR,
    second_economy   VARCHAR,
    government       VARCHAR,
    security         VARCHAR,
    population       BIGINT,
    first_visited    TIMESTAMPTZ,
    last_visited     TIMESTAMPTZ,
    visit_count      INTEGER DEFAULT 1
);

-- Jumps (FSDJump — core travel log, drives 3D map)
CREATE TABLE IF NOT EXISTS jumps (
    jump_id          VARCHAR PRIMARY KEY,  -- timestamp + system_address
    timestamp        TIMESTAMPTZ NOT NULL,
    star_system      VARCHAR NOT NULL,
    system_address   BIGINT,
    x                DOUBLE,
    y                DOUBLE,
    z                DOUBLE,
    body             VARCHAR,
    body_id          BIGINT,
    body_type        VARCHAR,
    jump_dist        DOUBLE,              -- ly jumped
    fuel_used        DOUBLE,
    fuel_level       DOUBLE,
    allegiance       VARCHAR,
    economy          VARCHAR,
    government       VARCHAR,
    security         VARCHAR,
    population       BIGINT,
    powerplay_state  VARCHAR,
    taxi             BOOLEAN,
    multicrew        BOOLEAN,
    source_file      VARCHAR
);

-- Jump Powers (many-to-one with jumps)
CREATE TABLE IF NOT EXISTS jump_powers (
    jump_id          VARCHAR,
    power            VARCHAR,
    PRIMARY KEY (jump_id, power)
);

-- Locations (Location event — where player spawns in)
CREATE TABLE IF NOT EXISTS locations (
    location_id      VARCHAR PRIMARY KEY,
    timestamp        TIMESTAMPTZ NOT NULL,
    star_system      VARCHAR,
    system_address   BIGINT,
    x                DOUBLE,
    y                DOUBLE,
    z                DOUBLE,
    body             VARCHAR,
    body_id          BIGINT,
    body_type        VARCHAR,
    docked           BOOLEAN,
    station_name     VARCHAR,
    station_type     VARCHAR,
    market_id        BIGINT,
    dist_from_star   DOUBLE,
    allegiance       VARCHAR,
    economy          VARCHAR,
    government       VARCHAR,
    security         VARCHAR,
    population       BIGINT,
    source_file      VARCHAR
);

-- Factions (denormalized per system visit — from jumps & locations)
CREATE TABLE IF NOT EXISTS system_factions (
    id               VARCHAR PRIMARY KEY,
    source_event     VARCHAR,             -- 'FSDJump' or 'Location'
    source_id        VARCHAR,             -- jump_id or location_id
    system_address   BIGINT,
    timestamp        TIMESTAMPTZ,
    faction_name     VARCHAR,
    faction_state    VARCHAR,
    government       VARCHAR,
    influence        DOUBLE,
    allegiance       VARCHAR,
    happiness        VARCHAR,
    my_reputation    DOUBLE
);

-- Stations (deduplicated dock data)
CREATE TABLE IF NOT EXISTS stations (
    market_id        BIGINT PRIMARY KEY,
    station_name     VARCHAR,
    station_type     VARCHAR,
    star_system      VARCHAR,
    system_address   BIGINT,
    allegiance       VARCHAR,
    government       VARCHAR,
    economy          VARCHAR,
    dist_from_star   DOUBLE,
    first_docked     TIMESTAMPTZ,
    last_docked      TIMESTAMPTZ,
    dock_count       INTEGER DEFAULT 1
);

-- Dock Events
CREATE TABLE IF NOT EXISTS docked (
    dock_id          VARCHAR PRIMARY KEY,
    timestamp        TIMESTAMPTZ NOT NULL,
    station_name     VARCHAR,
    station_type     VARCHAR,
    star_system      VARCHAR,
    system_address   BIGINT,
    market_id        BIGINT,
    allegiance       VARCHAR,
    government       VARCHAR,
    economy          VARCHAR,
    dist_from_star   DOUBLE,
    active_fine      BOOLEAN,
    taxi             BOOLEAN,
    multicrew        BOOLEAN,
    source_file      VARCHAR
);

-- Missions (accepted)
CREATE TABLE IF NOT EXISTS missions (
    mission_id       BIGINT PRIMARY KEY,
    timestamp        TIMESTAMPTZ NOT NULL,
    faction          VARCHAR,
    name             VARCHAR,
    localised_name   VARCHAR,
    target_type      VARCHAR,
    target_faction   VARCHAR,
    kill_count       INTEGER,
    destination_system VARCHAR,
    destination_station VARCHAR,
    expiry           TIMESTAMPTZ,
    wing             BOOLEAN,
    influence        VARCHAR,
    reputation       VARCHAR,
    reward           BIGINT,
    source_file      VARCHAR
);

-- Mission Completions
CREATE TABLE IF NOT EXISTS mission_completions (
    id               VARCHAR PRIMARY KEY,
    mission_id       BIGINT,
    timestamp        TIMESTAMPTZ NOT NULL,
    faction          VARCHAR,
    name             VARCHAR,
    kill_count       INTEGER,
    destination_system VARCHAR,
    destination_station VARCHAR,
    reward           BIGINT,
    source_file      VARCHAR
);

-- Bounties
CREATE TABLE IF NOT EXISTS bounties (
    bounty_id        VARCHAR PRIMARY KEY,
    timestamp        TIMESTAMPTZ NOT NULL,
    target           VARCHAR,
    target_localised VARCHAR,
    total_reward     BIGINT,
    victim_faction   VARCHAR,
    source_file      VARCHAR
);

-- Bounty Reward breakdown (by faction)
CREATE TABLE IF NOT EXISTS bounty_rewards (
    bounty_id        VARCHAR,
    faction          VARCHAR,
    reward           BIGINT,
    PRIMARY KEY (bounty_id, faction)
);

-- Body Scans (stars and planets)
CREATE TABLE IF NOT EXISTS scans (
    scan_id          VARCHAR PRIMARY KEY,
    timestamp        TIMESTAMPTZ NOT NULL,
    scan_type        VARCHAR,
    body_name        VARCHAR,
    body_id          BIGINT,
    star_system      VARCHAR,
    system_address   BIGINT,
    distance_from_arrival DOUBLE,
    -- Star fields
    star_type        VARCHAR,
    subclass         BIGINT,
    stellar_mass     DOUBLE,
    radius           DOUBLE,
    surface_temp     DOUBLE,
    luminosity       VARCHAR,
    age_my           INTEGER,
    -- Planet/moon fields
    planet_class     VARCHAR,
    mass_em          DOUBLE,
    landable         BOOLEAN,
    atmosphere       VARCHAR,
    volcanism        VARCHAR,
    surface_gravity  DOUBLE,
    surface_pressure DOUBLE,
    tidal_lock       BOOLEAN,
    -- Orbital elements
    semi_major_axis  DOUBLE,
    eccentricity     DOUBLE,
    orbital_incl     DOUBLE,
    orbital_period   DOUBLE,
    rotation_period  DOUBLE,
    axial_tilt       DOUBLE,
    -- Discovery
    was_discovered   BOOLEAN,
    was_mapped       BOOLEAN,
    source_file      VARCHAR
);

-- Materials Collected
CREATE TABLE IF NOT EXISTS materials_collected (
    id               VARCHAR PRIMARY KEY,
    timestamp        TIMESTAMPTZ NOT NULL,
    category         VARCHAR,
    name             VARCHAR,
    name_localised   VARCHAR,
    count            INTEGER,
    source_file      VARCHAR
);

-- Mining Refined
CREATE TABLE IF NOT EXISTS mining_refined (
    id               VARCHAR PRIMARY KEY,
    timestamp        TIMESTAMPTZ NOT NULL,
    type             VARCHAR,
    type_localised   VARCHAR,
    source_file      VARCHAR
);

-- Engineer Crafting Sessions
CREATE TABLE IF NOT EXISTS engineer_crafts (
    craft_id         VARCHAR PRIMARY KEY,
    timestamp        TIMESTAMPTZ NOT NULL,
    slot             VARCHAR,
    module           VARCHAR,
    engineer         VARCHAR,
    engineer_id      BIGINT,
    blueprint_id     BIGINT,
    blueprint_name   VARCHAR,
    level            INTEGER,
    quality          DOUBLE,
    experimental_effect VARCHAR,
    experimental_effect_localised VARCHAR,
    source_file      VARCHAR
);

-- Engineer Craft Ingredients
CREATE TABLE IF NOT EXISTS engineer_craft_ingredients (
    craft_id         VARCHAR,
    name             VARCHAR,
    name_localised   VARCHAR,
    count            INTEGER,
    PRIMARY KEY (craft_id, name)
);

-- Engineer Craft Result Modifiers
CREATE TABLE IF NOT EXISTS engineer_craft_modifiers (
    craft_id         VARCHAR,
    label            VARCHAR,
    value            DOUBLE,
    original_value   DOUBLE,
    less_is_good     BOOLEAN,
    PRIMARY KEY (craft_id, label)
);

-- Ship Loadouts (snapshot per LoadGame or dock)
CREATE TABLE IF NOT EXISTS loadouts (
    loadout_id       VARCHAR PRIMARY KEY,
    timestamp        TIMESTAMPTZ NOT NULL,
    ship             VARCHAR,
    ship_id          BIGINT,
    ship_name        VARCHAR,
    ship_ident       VARCHAR,
    hull_value       BIGINT,
    modules_value    BIGINT,
    hull_health      DOUBLE,
    unladen_mass     DOUBLE,
    cargo_capacity   INTEGER,
    max_jump_range   DOUBLE,
    fuel_main        DOUBLE,
    fuel_reserve     DOUBLE,
    rebuy            BIGINT,
    source_file      VARCHAR
);

-- Ship Modules (from Loadout)
CREATE TABLE IF NOT EXISTS ship_modules (
    loadout_id       VARCHAR,
    slot             VARCHAR,
    item             VARCHAR,
    is_on            BOOLEAN,
    priority         INTEGER,
    health           DOUBLE,
    value            BIGINT,
    -- Engineering
    engineer         VARCHAR,
    blueprint_name   VARCHAR,
    blueprint_level  INTEGER,
    blueprint_quality DOUBLE,
    experimental_effect VARCHAR,
    PRIMARY KEY (loadout_id, slot)
);

-- FSS Signals Discovered
CREATE TABLE IF NOT EXISTS fss_signals (
    id               VARCHAR PRIMARY KEY,
    timestamp        TIMESTAMPTZ NOT NULL,
    system_address   BIGINT,
    signal_name      VARCHAR,
    signal_name_localised VARCHAR,
    signal_type      VARCHAR,
    source_file      VARCHAR
);
