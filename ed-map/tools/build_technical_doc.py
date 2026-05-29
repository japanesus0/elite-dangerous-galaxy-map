#!/usr/bin/env python3
"""
Build the Elite Dangerous Galaxy Map — Technical Reference as a .docx.

Run via docker:
    docker run --rm -v "$(pwd):/work" -w /work \
        python:3.12-slim sh -c \
        "pip install -q python-docx==1.1.2 && python tools/build_technical_doc.py"

Output: docs/EliteGalaxyMap-TechnicalReference.docx
"""

from pathlib import Path

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Pt, RGBColor, Cm


# ── styling helpers (shared with the user guide builder) ───────

ED_BLUE   = RGBColor(0x1A, 0x9F, 0xFF)
ED_AMBER  = RGBColor(0xFF, 0xAB, 0x00)
ED_DIM    = RGBColor(0x4A, 0x7A, 0x9B)
ED_DARK   = RGBColor(0x10, 0x18, 0x28)
ED_RED    = RGBColor(0xFF, 0x17, 0x44)
ED_GREEN  = RGBColor(0x00, 0xA8, 0x55)
ED_PURPLE = RGBColor(0x8E, 0x44, 0xAD)


def shade(cell, hex_no_hash):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_no_hash)
    tc_pr.append(shd)


def set_cell_borders(cell, color="9bb1c8"):
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = OxmlElement("w:tcBorders")
    for side in ("top", "left", "bottom", "right"):
        b = OxmlElement(f"w:{side}")
        b.set(qn("w:val"), "single")
        b.set(qn("w:sz"), "4")
        b.set(qn("w:color"), color)
        borders.append(b)
    tc_pr.append(borders)


def add_run(para, text, *, bold=False, italic=False, color=None,
            size=None, font="Calibri"):
    r = para.add_run(text)
    r.font.name = font
    if bold:    r.bold = True
    if italic:  r.italic = True
    if color:   r.font.color.rgb = color
    if size:    r.font.size = Pt(size)
    return r


def add_code_block(doc, lines, *, lang_label=None):
    if lang_label:
        lp = doc.add_paragraph()
        lp.paragraph_format.space_before = Pt(6)
        lp.paragraph_format.space_after  = Pt(0)
        add_run(lp, lang_label, bold=True, color=ED_DIM, size=8, font="Consolas")
    p = doc.add_paragraph()
    p.paragraph_format.left_indent  = Cm(0.5)
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after  = Pt(8)
    for i, line in enumerate(lines):
        if i:
            p.add_run().add_break()
        r = p.add_run(line)
        r.font.name  = "Consolas"
        r.font.size  = Pt(9)
        r.font.color.rgb = ED_DARK
    pPr = p._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), "f1f4f7")
    pPr.append(shd)


def configure_styles(doc):
    base = doc.styles["Normal"]
    base.font.name = "Calibri"
    base.font.size = Pt(11)

    h1 = doc.styles["Heading 1"]
    h1.font.name = "Calibri"; h1.font.size = Pt(20)
    h1.font.bold = True; h1.font.color.rgb = ED_BLUE

    h2 = doc.styles["Heading 2"]
    h2.font.name = "Calibri"; h2.font.size = Pt(15)
    h2.font.bold = True; h2.font.color.rgb = ED_BLUE

    h3 = doc.styles["Heading 3"]
    h3.font.name = "Calibri"; h3.font.size = Pt(12)
    h3.font.bold = True; h3.font.color.rgb = ED_DIM


def two_col_table(doc, header_left, header_right, rows, *, col0_cm=4.5):
    t = doc.add_table(rows=len(rows) + 1, cols=2)
    t.autofit = False
    t.columns[0].width = Cm(col0_cm)
    t.columns[1].width = Cm(16 - col0_cm)
    h0, h1 = t.rows[0].cells
    h0.width = Cm(col0_cm); h1.width = Cm(16 - col0_cm)
    add_run(h0.paragraphs[0], header_left,  bold=True, color=ED_BLUE)
    add_run(h1.paragraphs[0], header_right, bold=True, color=ED_BLUE)
    shade(h0, "eef4fa"); shade(h1, "eef4fa")
    set_cell_borders(h0); set_cell_borders(h1)
    for i, (a, b) in enumerate(rows, start=1):
        c0, c1 = t.rows[i].cells
        c0.width = Cm(col0_cm); c1.width = Cm(16 - col0_cm)
        c0.text = ""; c1.text = ""
        add_run(c0.paragraphs[0], a, font="Consolas", size=9, color=ED_DARK)
        c1.paragraphs[0].add_run(b)
        for c in (c0, c1):
            set_cell_borders(c)
            c.vertical_alignment = WD_ALIGN_VERTICAL.TOP


# ── content sections ───────────────────────────────────────────

def title_page(doc):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_run(p, "Elite Dangerous", bold=True, color=ED_BLUE,  size=28)
    p.add_run().add_break()
    add_run(p, "Galaxy Map",       bold=True, color=ED_AMBER, size=28)

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_run(sub, "Technical Reference", italic=True, color=ED_DIM, size=16)

    doc.add_paragraph()
    desc = doc.add_paragraph()
    desc.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_run(desc,
            "Architecture, data model, ETL design, materialised-view "
            "strategy, front-end module graph, and operational guidance "
            "for developers and operators.",
            italic=True, color=ED_DIM, size=11)

    doc.add_paragraph()
    info = doc.add_paragraph()
    info.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_run(info,
            "Audience: software engineers extending or operating the system  •  "
            "Companion to the User Guide",
            color=ED_DIM, size=9)
    doc.add_page_break()


def section_intro(doc):
    doc.add_heading("1. Introduction", level=1)
    doc.add_paragraph(
        "This document describes the internal architecture of the Elite "
        "Dangerous Galaxy Map. It is intended for engineers who want to "
        "extend, debug, or operate the system rather than just use it. "
        "Sections cover the data model, the ETL pipeline, the HTTP API, "
        "the materialised-view performance strategy, the front-end module "
        "graph, the build and deployment topology, the test suite, and a "
        "set of explicit extension points."
    )

    doc.add_heading("Repository layout", level=2)
    add_code_block(doc, [
        "EliteDangerous/",
        "├── .gitignore",
        "├── JournalLogs/                    # drop folder watched by elite-watcher",
        "│   └── Loaded/                     # files moved here once parsed",
        "└── ed-map/",
        "    ├── docker-compose.yml",
        "    ├── Dockerfile.{etl,map,watcher,test}",
        "    ├── .env.example                # template; copy to .env locally",
        "    ├── etl.py                      # parsers + bulk insert + matview refresh",
        "    ├── watcher.py                  # long-running incremental loader",
        "    ├── map_api.py                  # FastAPI server",
        "    ├── schema.sql                  # tables + indexes + materialised view",
        "    ├── map.html                    # 218-line markup; CSS + JS extracted",
        "    ├── static/",
        "    │   ├── map.css",
        "    │   ├── vendor/three.r128.min.js",
        "    │   └── js/                     # 9 ES modules, see §8",
        "    ├── tests/                      # pytest parser tests",
        "    ├── tools/                      # docs / housekeeping scripts",
        "    └── docs/",
    ])


def section_architecture(doc):
    doc.add_heading("2. Architecture Overview", level=1)

    doc.add_paragraph(
        "Four containers run on a private Docker network. PostgreSQL is "
        "the system of record. The watcher and ETL containers are "
        "interchangeable producers — same parsing logic, different "
        "trigger model. The map service is the only consumer."
    )

    doc.add_heading("Component diagram (text form)", level=2)
    add_code_block(doc, [
        "                        +----------------------------+",
        "  Frontier client  -->  |   JournalLogs/             |",
        "                        |   Journal*.log files       |",
        "                        +-------------+--------------+",
        "                                      |  poll every 30s",
        "                                      v",
        "                        +----------------------------+",
        "                        |   elite-watcher  (Python)  |",
        "                        |   import etl                |",
        "                        +-------------+--------------+",
        "                                      | bulk insert + refresh matview",
        "                                      v",
        "                        +----------------------------+",
        "                        |   postgres:16-alpine       |",
        "                        |   schema.sql + matview     |",
        "                        +-------------+--------------+",
        "                                      | psycopg2",
        "                                      v",
        "                        +----------------------------+",
        "                        |   elite-map  (FastAPI)     |",
        "                        |   map_api.py + static/     |",
        "                        +-------------+--------------+",
        "                                      | HTTP 8051",
        "                                      v",
        "                        +----------------------------+",
        "                        |   browser  (Three.js)      |",
        "                        +----------------------------+",
        "",
        "  elite-etl is the same image as elite-watcher, invoked",
        "  one-shot for bulk loads / --rebuild. Same code, same DB.",
    ])

    doc.add_heading("Trust and process boundaries", level=2)
    bullets = [
        "Everything runs on localhost. No external network calls at runtime.",
        "PostgreSQL is bound to the host on 5432 for direct DB tooling (DBeaver, psql). Comment the `ports:` block out if you don't want this exposed.",
        "The map service exposes 8051 on the host. CORS is permissive by default — set ALLOWED_ORIGINS in .env to lock it down for split deployments.",
        "Journal logs are mounted read-write into elite-watcher (so it can move processed files to Loaded/) and read-only into elite-etl.",
    ]
    for b in bullets:
        doc.add_paragraph(b, style="List Bullet")


def section_stack(doc):
    doc.add_heading("3. Technology Stack", level=1)

    rows = [
        ("Python 3.12-slim",       "Runtime for ETL, watcher, and map API. Slim variant chosen for image size."),
        ("PostgreSQL 16-alpine",   "System of record. Schema applied via /docker-entrypoint-initdb.d/."),
        ("psycopg2-binary 2.9.10", "Database driver for all Python services. Binary build avoids the libpq compile step."),
        ("FastAPI 0.115 + uvicorn 0.32", "HTTP layer for the map API. Standard install (uvicorn[standard]) for the high-perf event loop."),
        ("Three.js r128",          "WebGL renderer. Vendored locally at /static/vendor/three.r128.min.js — no CDN dependency."),
        ("python-docx 1.1.2",      "Used by tools/build_user_guide.py and this generator. Not a runtime dependency."),
        ("pytest 8.3.3",           "Parser test suite. Run via the elite-tests profile."),
        ("Docker Compose v2",      "Orchestration. Service profiles separate the test container from the runtime stack."),
    ]
    two_col_table(doc, "Component", "Role", rows, col0_cm=5.5)


def section_data_model(doc):
    doc.add_heading("4. Data Model", level=1)
    doc.add_paragraph(
        "The schema is normalised against the journal-log event types but "
        "deliberately flat — no foreign keys, no triggers. Every row is "
        "keyed by either a deterministic hash of (event timestamp, event "
        "fields, source file) or by a Frontier-issued natural key like "
        "MarketID or MissionID. This makes the load idempotent under "
        "ON CONFLICT DO NOTHING."
    )

    doc.add_heading("Tables", level=2)
    rows = [
        ("sessions",            "One row per LoadGame event. Carries commander FID, ship at login, fuel, credits, game version."),
        ("commanders",          "One row per FID. first_seen / last_seen are upserted from every event referencing the FID."),
        ("ranks",               "One row per Rank event. Combat / trade / explore / etc. progression."),
        ("jumps",               "Core table. One row per FSDJump. x/y/z/system_address are the foundation of the map."),
        ("jump_powers",         "Many-to-many — one row per (jump_id, power) pair from the FSDJump 'Powers' array."),
        ("star_systems",        "Unique-per-system_address upsert. visit_count incremented per FSDJump + Location reference."),
        ("locations",           "One row per Location event (any time the game writes a fresh location, e.g. game start, supercruise enter)."),
        ("system_factions",     "Faction snapshot per FSDJump or Location. Composite id includes source_event so the same faction in both events does NOT collide."),
        ("stations",            "Unique-per-MarketID upsert. dock_count incremented per Docked event."),
        ("docked",              "One row per Docked event with full snapshot (allegiance, government, economy, distance from star)."),
        ("missions",            "One row per MissionAccepted (keyed on Frontier's MissionID)."),
        ("mission_completions", "One row per MissionCompleted, joined back to missions on mission_id."),
        ("bounties",            "One row per Bounty event."),
        ("bounty_rewards",      "Many-to-many — per-faction reward split for a bounty."),
        ("scans",               "One row per Scan event. Mixed star + planet schema (NULL fields for the wrong kind)."),
        ("materials_collected", "One row per MaterialCollected with category and count."),
        ("mining_refined",      "One row per MiningRefined event."),
        ("engineer_crafts",     "One row per EngineerCraft event."),
        ("engineer_craft_ingredients", "Many-to-many — ingredients consumed in a craft."),
        ("engineer_craft_modifiers",   "Many-to-many — module modifiers produced by a craft."),
        ("loadouts",            "One row per Loadout event. Drives the ship viewer via binary search on timestamp."),
        ("ship_modules",        "Per-loadout module loadout including blueprint name and engineering level."),
        ("fss_signals",         "One row per FSSSignalDiscovered. signal_type prefers Frontier's SignalType field, falls back to localised text only for symbol names."),
        ("processed_logs",      "ETL/watcher ledger. Used to skip files we've already parsed."),
        ("jump_aggregates",     "Materialised view (§6). Pre-joins jumps with discoveries / earth-likes / bounties / materials / missions / sessions / minerals."),
    ]
    two_col_table(doc, "Table", "Purpose", rows, col0_cm=5.5)

    doc.add_heading("Deterministic row IDs", level=2)
    doc.add_paragraph(
        "Most fact tables (jumps, scans, bounties, etc.) use a 16-character "
        "MD5 prefix derived from the event timestamp + source file + "
        "discriminating fields. This is computed in etl.row_id() and means "
        "the same event parsed twice produces the same primary key, so "
        "ON CONFLICT DO NOTHING keeps the load idempotent. The MD5 here is "
        "an identifier hash, not a security primitive."
    )
    add_code_block(doc, [
        "def row_id(*parts) -> str:",
        '    key = "|".join(str(p) for p in parts)',
        "    return hashlib.md5(key.encode()).hexdigest()[:16]",
    ], lang_label="etl.py")


def section_etl(doc):
    doc.add_heading("5. ETL Pipeline", level=1)
    doc.add_paragraph(
        "Both the batch loader (elite-etl) and the long-running watcher "
        "share a single function — process_files_list — defined in etl.py. "
        "Two trigger surfaces, one parsing path."
    )

    doc.add_heading("Stages", level=2)
    rows = [
        ("1. Discover",   "Caller passes a list of Path objects (CLI globs JournalLogs/**/Journal*.log; watcher diffs the filesystem against processed_logs)."),
        ("2. Skip-known", "Files already in processed_logs are dropped from the work list (unless --rebuild)."),
        ("3. Parse",      "Each line is JSON-decoded; the event['event'] field selects a parser via EVENT_PARSERS dispatch table."),
        ("4. Accumulate", "Each parser returns a dict of {table_name: [rows]}. Results are accumulated across all files in a single batch."),
        ("5. Bulk insert", "execute_values with page_size=500 + ON CONFLICT DO NOTHING for fact tables."),
        ("6. Upsert",     "star_systems / stations / commanders go through upsert_* functions that aggregate visit / dock / first-seen / last-seen counters."),
        ("7. Refresh",    "refresh_jump_aggregates is called at the end of every load. CONCURRENTLY when possible (see §6)."),
        ("8. Mark",       "Filenames are written to processed_logs in a final transaction so a crash mid-load doesn't leave stale ledger entries."),
    ]
    two_col_table(doc, "Stage", "Detail", rows, col0_cm=3.5)

    doc.add_heading("Per-event parser pattern", level=2)
    doc.add_paragraph(
        "Each parser is pure — no DB access, no shared state. Inputs are "
        "(event_dict, source_filename); the output is a {table: [row_dicts]} "
        "mapping. This shape lets the test suite exercise parsers in "
        "isolation (see §11)."
    )
    add_code_block(doc, [
        "def parse_fsdjump(ev, src):",
        '    ts      = parse_ts(ev.get("timestamp"))',
        "    x, y, z = _pos(ev)",
        '    jump_id = row_id(ev.get("timestamp", ""),',
        '                     str(ev.get("SystemAddress", "")))',
        "    return {",
        '        "jumps":            [...],     # the main row',
        '        "jump_powers":      [...],     # 0..N rows',
        '        "star_systems_raw": [...],     # for upsert path',
        '        "system_factions":  [...],     # 0..N rows',
        "    }",
    ], lang_label="etl.py")

    doc.add_heading("Conflict-resolution strategies", level=2)
    rows = [
        ("Fact tables",     "INSERT ... ON CONFLICT (pk) DO NOTHING. Duplicate inserts are safe and silent."),
        ("star_systems",    "Upsert keyed on system_address. visit_count is incremented; coordinates are filled in if NULL; last_visited takes GREATEST."),
        ("stations",        "Upsert keyed on market_id. dock_count incremented; last_docked takes GREATEST."),
        ("commanders",      "Upsert keyed on fid. first_seen kept; last_seen takes GREATEST."),
        ("system_factions", "Composite hash includes source_event — FSDJump and Location reporting the same faction at the same timestamp now produce different rows (regression-tested)."),
    ]
    two_col_table(doc, "Target", "Strategy", rows, col0_cm=4.5)

    doc.add_heading("CLI surface", level=2)
    add_code_block(doc, [
        "# Normal incremental load — skips files already in processed_logs",
        "docker compose run --rm elite-etl",
        "",
        "# Drop everything, re-parse all logs from scratch",
        "docker compose run --rm elite-etl --rebuild",
        "",
        "# Per-file progress (large loads)",
        "docker compose run --rm elite-etl --verbose",
    ])


def section_watcher(doc):
    doc.add_heading("6. Watcher Service", level=1)
    doc.add_paragraph(
        "The watcher is a thin polling loop around the same parsing engine. "
        "Its responsibilities:"
    )
    bullets = [
        "On startup, run move_already_processed — sweep any files the ETL has already loaded (per processed_logs) into JournalLogs/Loaded/. This handles the boundary case where you ran elite-etl manually before starting the watcher.",
        "Every POLL_INTERVAL seconds (default 30), enumerate JournalLogs/*.log and diff against processed_logs.",
        "For each new file: parse + bulk insert + refresh matview + mark in processed_logs + move to Loaded/. The matview refresh comes for free because process_files_list calls it.",
        "Connection-loss recovery: a top-level psycopg2.OperationalError handler closes the broken connection, sleeps 5 s, reconnects, and re-ensures the processed_logs table.",
    ]
    for b in bullets:
        doc.add_paragraph(b, style="List Bullet")

    doc.add_paragraph(
        "There is no in-memory state beyond the open connection — restart "
        "the watcher freely; the processed_logs ledger is the source of "
        "truth for what has already been loaded."
    )


def section_matview(doc):
    doc.add_heading("7. The jump_aggregates Materialised View", level=1)

    doc.add_paragraph(
        "The /api/jumps endpoint historically computed enrichment "
        "(discoveries, earth-likes, bounties, materials, missions, "
        "sessions, minerals) for every jump on every request via a "
        "seven-CTE join over jumps. At ~5 K jumps and ~17 K scans this "
        "took several hundred milliseconds; at 10× the data it would "
        "blow out cache locality and OS read-ahead."
    )

    doc.add_paragraph(
        "The materialised view jump_aggregates pre-computes that result, "
        "keyed on jump_id and indexed on (jump_time, source_file). "
        "/api/jumps now collapses to a single ordered scan plus an "
        "optional commander filter via:"
    )
    add_code_block(doc, [
        "WHERE source_file IN (",
        "  SELECT source_file FROM sessions WHERE fid = %s",
        ")",
    ], lang_label="map_api.py — /api/jumps")

    doc.add_heading("Refresh strategy", level=2)
    doc.add_paragraph(
        "etl.refresh_jump_aggregates() is called at the end of every "
        "process_files_list() invocation, plus eagerly on the watcher's "
        "startup and on the ETL's no-op branch (so legacy databases that "
        "predate the matview pick it up the first time you run any load "
        "command)."
    )
    doc.add_paragraph(
        "REFRESH MATERIALIZED VIEW CONCURRENTLY is used when the view is "
        "already populated — concurrent reads continue while the rebuild "
        "runs. This requires the unique index idx_jump_aggregates_jump_id, "
        "which is part of schema.sql. On the very first refresh (before "
        "the view has any rows) Postgres rejects CONCURRENTLY, so we "
        "detect the unpopulated state via pg_class.relispopulated and "
        "drop to a plain REFRESH for that single call."
    )

    doc.add_heading("Lateral joins", level=2)
    doc.add_paragraph(
        "The view body uses LEFT JOIN LATERAL to compute each enrichment "
        "subselect once per jump row. The previous CTE-based query "
        "produced the same result but had a query plan that depended on "
        "Postgres choosing the right join order; the lateral form is "
        "explicit about per-row evaluation and produces a stable plan."
    )

    doc.add_heading("Failure surface", level=2)
    doc.add_paragraph(
        "If the matview is missing entirely (e.g., an extremely old DB "
        "that has never run a refresh), /api/jumps returns HTTP 503 with "
        "a clear remediation message instead of silently slow-pathing. "
        "/api/health distinguishes 'ok' from 'degraded' (matview missing) "
        "from 'down' (DB unreachable) for downstream monitoring."
    )


def section_http_api(doc):
    doc.add_heading("8. HTTP API", level=1)
    doc.add_paragraph(
        "FastAPI app served by uvicorn on MAP_PORT (default 8051). All "
        "endpoints are GET, all return JSON, and all are read-only. "
        "Connections to PostgreSQL are opened per-request and closed in "
        "a finally block — there is no pool, but request volume from a "
        "single browser is trivial."
    )

    rows = [
        ("/",                          "Serves map.html"),
        ("/static/...",                "Vendored Three.js, CSS, ES modules"),
        ("/api/health",                "Liveness + matview readiness"),
        ("/api/jumps",                 "Reads from jump_aggregates"),
        ("/api/jumps?commander=<fid>", "Same, filtered to one commander"),
        ("/api/system/<address>",      "Per-visit drill-down. Optional ?visit=<iso ts>"),
        ("/api/stats",                 "Lifetime totals (parameterisable by commander)"),
        ("/api/commanders",            "Distinct commanders + jump counts"),
        ("/api/loadouts",              "All loadouts ordered by timestamp"),
        ("/api/ship?before=<ts>",      "Single most-recent loadout at-or-before ts"),
        ("/api/bounties/summary",      "Aggregated combat (totals + by_ship + by_faction + by_year + top_kills). Accepts ?before=<ts>."),
        ("/api/mining/summary",        "Aggregated mining (totals + by_material + by_year + recent). Accepts ?before=<ts>."),
    ]
    two_col_table(doc, "Endpoint", "Purpose", rows, col0_cm=6.5)

    doc.add_heading("CORS", level=2)
    doc.add_paragraph(
        "FastAPI is wrapped in CORSMiddleware with allow_origins driven by "
        "the ALLOWED_ORIGINS env var (default '*'). Methods are restricted "
        "to GET; credentials are off. For split deployments (e.g. running "
        "the map frontend on a CDN), set ALLOWED_ORIGINS explicitly."
    )

    doc.add_heading("Visit scoping for /api/system", level=2)
    doc.add_paragraph(
        "Without ?visit=, the endpoint defaults to the FIRST visit of a "
        "system, which is misleading if you've returned later. The map "
        "frontend always passes the clicked jump's timestamp so the "
        "drill-down is scoped to that exact arrival window — scans and "
        "bounties are bounded by [arrival_ts, next_jump_out)."
    )


def section_frontend(doc):
    doc.add_heading("9. Front-end Architecture", level=1)
    doc.add_paragraph(
        "The map page is plain ES modules — no bundler, no transpiler. "
        "Three.js is loaded as a UMD global before the module entry point "
        "so every module just reads window.THREE. Modules use full file "
        "extensions (./foo.js), which is what native browser ESM requires."
    )

    doc.add_heading("Module boundaries", level=2)
    rows = [
        ("constants.js", "SOL_POS / SGRA_POS / COLONIA_POS, COLOR, SPEED_CFG, SHIP_DISPLAY_NAMES, fmtK / fmtCr."),
        ("state.js",     "Single shared mutable object — every cross-module reference goes through state.X. Replaces the original 'globals' model with explicit dependencies."),
        ("scene.js",     "Three.js scene + camera + renderer + custom orbit controls + starfield + procedural milky-way disk + landmark glows."),
        ("jumps.js",     "buildJumpScene, the active-jump halo (dual material), buildLiveStatsIndex (prefix sums), updateLiveStats."),
        ("timeline.js",  "setIndex (the pivot of the whole UI), play / pause / step, last-N filter, bounty activity chart."),
        ("panels.js",    "System detail, bounty log, mining log, system info, hover tooltip, raycaster click handler."),
        ("ship-viewer.js", "Ship wireframe meshes, sub-scene + camera, loadout binary search."),
        ("data.js",      "loadData (initial), reloadScene (commander switch), updateStats, _applyJumpsToScene."),
        ("main.js",      "Entry point. Imports everything, kicks off loadData, runs the render loop with ship sub-scene scissor inset."),
    ]
    two_col_table(doc, "Module", "Responsibility", rows, col0_cm=4.5)

    doc.add_heading("Dependency direction", level=2)
    add_code_block(doc, [
        "                    constants.js   state.js",
        "                         |             |",
        "                         v             v",
        "                       scene.js  <----+",
        "                         |            |",
        "                         v            |",
        "                       jumps.js  <----+",
        "                       /     \\        |",
        "                      v       v       |",
        "                ship-viewer  panels   |",
        "                       \\    /  |      |",
        "                        v  v   v      |",
        "                      timeline.js  <--+",
        "                            |",
        "                            v",
        "                          data.js",
        "                            |",
        "                            v",
        "                          main.js",
        "",
        "  Arrows: 'imports from'. No cycles.",
    ])

    doc.add_heading("Why a shared mutable object instead of getters/setters?", level=2)
    doc.add_paragraph(
        "The original 2,000-line script kept ~20 globals shared across "
        "what would become module boundaries. The shortest path that "
        "preserves semantics exactly is to consolidate those globals "
        "into state.js. ES module bindings give every importer the same "
        "object reference, so writes from one module are immediately "
        "visible to all others. This avoids the TDZ and circular-import "
        "footguns that come from an aggressive setter/getter split."
    )

    doc.add_heading("DOM lifecycle", level=2)
    doc.add_paragraph(
        "<script type=\"module\"> is auto-deferred — it runs after the HTML "
        "body has been parsed. Module top-level code can therefore call "
        "document.getElementById and addEventListener freely; no extra "
        "DOMContentLoaded wrapper is needed. A static cross-reference "
        "check (tools/tests/check_imports.cjs) verifies every "
        "getElementById argument matches an id= attribute in map.html."
    )


def section_threejs(doc):
    doc.add_heading("10. Three.js Scene Composition", level=1)

    doc.add_heading("Render passes per frame", level=2)
    rows = [
        ("renderer.clear()",                        "Manual clear because autoClear is off (we do scissor inset for the ship viewer)."),
        ("renderer.render(scene, camera)",          "Main 3D galaxy."),
        ("setScissorTest + setScissor + setViewport", "Restrict the next render to the ship-viewer rectangle in CSS pixel space."),
        ("clearDepth()",                            "So the ship doesn't z-fight against the main scene's depth buffer."),
        ("renderer.render(shipScene, shipCamera)",  "Sub-scene with the wireframe ship."),
        ("setScissorTest(false) + setViewport(full)", "Restore for the next frame."),
    ]
    two_col_table(doc, "Step", "Why", rows, col0_cm=6.5)

    doc.add_heading("Active-jump halo: two materials, one geometry", level=2)
    doc.add_paragraph(
        "A single 1-vertex BufferGeometry stores the active jump's world "
        "position. Two THREE.Points objects share that geometry but use "
        "different PointsMaterials:"
    )
    bullets = [
        "World-space halo: sizeAttenuation: true, size dynamically scaled (8..600) by orbit distance each frame so the angular size stays roughly constant from Sol-zoom to Sgr A*-zoom.",
        "Screen-space halo: sizeAttenuation: false, fixed 14 px. Provides a floor so the marker never collapses to a single pixel at extreme zoom-out.",
    ]
    for b in bullets:
        doc.add_paragraph(b, style="List Bullet")

    doc.add_heading("Custom orbit controls", level=2)
    doc.add_paragraph(
        "We do not pull OrbitControls — it lives in three.js' /examples/ "
        "tree and would force a separate vendored file. The custom "
        "implementation in scene.js maintains spherical {r, phi, theta} "
        "around state.target, with the standard left-drag (orbit), "
        "right-drag (pan), wheel (zoom) bindings. Pan distance scales "
        "with r so it feels consistent at every zoom level."
    )

    doc.add_heading("Procedural milky way", level=2)
    doc.add_paragraph(
        "buildMilkyWay() draws to a 1024×1024 canvas, layers a diffuse "
        "disk gradient + four log-spiral arms drawn with shadow-blurred "
        "strokes + a soft galactic bar + a bulge gradient + a bright core. "
        "The canvas is wrapped as a CanvasTexture and applied to a "
        "PlaneGeometry(116000, 116000) rotated to lie in the galactic "
        "plane at SgrA*'s coordinates. renderOrder = -1 keeps it behind "
        "everything else."
    )


def section_performance(doc):
    doc.add_heading("11. Performance Strategies", level=1)

    doc.add_heading("Server-side", level=2)
    rows = [
        ("Materialised view",      "Pre-joins the seven-way enrichment query so /api/jumps is a single ordered scan. ~10× speedup at current scale."),
        ("execute_values, page=500", "psycopg2's bulk insert path. Roughly 5–10× faster than per-row execute()."),
        ("Indexes on timestamp + system_address", "Every panel and the matview's lateral joins are time-bounded; these indexes prevent seq scans."),
        ("processed_logs ledger",  "Skips re-parsing files we've already loaded. The watcher only opens new files."),
    ]
    two_col_table(doc, "Technique", "Effect", rows, col0_cm=4.5)

    doc.add_heading("Client-side", level=2)
    rows = [
        ("Prefix-sum live stats",  "buildLiveStatsIndex precomputes cumulative arrays so updateLiveStats is O(1) per slider tick — no re-iteration over jumpsData."),
        ("Loadout binary search",  "/api/loadouts is fetched once at boot; resolveShipAt does an O(log n) bisect on timestamp instead of per-tick fetch."),
        ("Hover throttle",         "Raycaster only runs every 4 frames, and skips entirely while follow-cam is on (where pointer is rarely meaningful)."),
        ("Diff-skip panel renders","Bounty + mining panels keep _lastBountyHTML / _lastMiningHTML and skip the innerHTML write if the new HTML is byte-identical."),
        ("setDrawRange instead of geometry rebuild", "Timeline scrubbing only changes the draw range on the same BufferGeometry. No buffer reallocation."),
        ("Debounced resize",       "Bounty chart rebuild is debounced 150 ms behind resize events."),
        ("Two-tier panel refresh", "While playing, panels refresh on a 1 s interval. While paused, they debounce 400 ms behind slider input."),
    ]
    two_col_table(doc, "Technique", "Effect", rows, col0_cm=5.5)


def section_build_deploy(doc):
    doc.add_heading("12. Build and Deployment", level=1)

    doc.add_heading("Compose topology", level=2)
    rows = [
        ("postgres",      "Always on. Initdb runs schema.sql on first boot via /docker-entrypoint-initdb.d/. Healthcheck is pg_isready."),
        ("elite-watcher", "Always on. Restart policy unless-stopped. Healthcheck inherited from the base; relies on postgres healthy gate."),
        ("elite-map",     "Always on. New: healthcheck against /api/health (every 15 s, 4 retries, 10 s start_period)."),
        ("elite-etl",     "On-demand only — `compose run --rm elite-etl`. Same image as watcher minus the loop."),
        ("elite-tests",   "Profile=test, only built/run on `compose --profile test run --rm elite-tests`. No DB dependency."),
    ]
    two_col_table(doc, "Service", "Lifecycle", rows, col0_cm=3.5)

    doc.add_heading("Image layout", level=2)
    rows = [
        ("Dockerfile.etl",     "Adds psycopg2-binary. Copies etl.py + schema.sql. ENTRYPOINT runs etl.py."),
        ("Dockerfile.watcher", "Adds psycopg2-binary. Copies etl.py + schema.sql + watcher.py. CMD runs watcher.py."),
        ("Dockerfile.map",     "Adds fastapi, uvicorn[standard], psycopg2-binary. Copies map_api.py + map.html + static/. CMD runs map_api.py."),
        ("Dockerfile.test",    "Adds pytest. Copies all Python sources + tests/. CMD runs pytest."),
    ]
    two_col_table(doc, "File", "Contents", rows, col0_cm=4.5)

    doc.add_heading("Environment variables", level=2)
    rows = [
        ("POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DB", "Used by Postgres init and by every Python service."),
        ("POSTGRES_HOST / POSTGRES_PORT", "Defaults to postgres:5432 inside compose, localhost:5432 if running scripts on the host."),
        ("ED_LOGS_DIR", "Where the ETL/watcher look for Journal*.log. Default /data/logs in containers."),
        ("POLL_INTERVAL", "Watcher cadence in seconds. Default 30."),
        ("MAP_HOST / MAP_PORT", "FastAPI bind. Default 0.0.0.0:8051."),
        ("ALLOWED_ORIGINS", "Comma-separated CORS allowlist. Default '*'. Set to your deployed origin to lock down."),
    ]
    two_col_table(doc, "Variable", "Purpose", rows, col0_cm=6.5)


def section_testing(doc):
    doc.add_heading("13. Testing", level=1)
    doc.add_paragraph(
        "19 parser tests in tests/test_parsers.py. They exercise the pure-"
        "Python parsing layer without touching PostgreSQL — conftest.py "
        "stubs psycopg2 at import time so the tests run on any machine "
        "with Python 3.12 and pytest installed."
    )

    doc.add_heading("Coverage", level=2)
    bullets = [
        "parse_ts: ISO-Z, offset, garbage input.",
        "row_id: determinism + collision-resistance.",
        "parse_fsdjump: row contents, deterministic id, jump_powers wiring, star_systems_raw shape, faction id uniqueness.",
        "Faction-id collision regression: confirms FSDJump and Location can no longer produce the same system_factions.id at the same timestamp (§4 fix).",
        "parse_scan: planet path + star path (mutually exclusive fields).",
        "parse_bounty: rewards link back to the parent bounty_id.",
        "parse_fsssignaldiscovered: explicit SignalType, $-prefix fallback to localised, plain named signals stay NULL (regression).",
        "parse_loadgame, parse_loadout (with engineering subfields), parse_engineercraft (ingredients + modifiers).",
    ]
    for b in bullets:
        doc.add_paragraph(b, style="List Bullet")

    doc.add_paragraph(
        "Run with:"
    )
    add_code_block(doc, ["docker compose --profile test run --rm elite-tests"])
    doc.add_paragraph("Typical wall-clock: under 0.1 s after image build.")

    doc.add_heading("Static cross-reference (front-end)", level=2)
    doc.add_paragraph(
        "tools/tests/check_imports.cjs walks every static/js/*.js, parses "
        "out exports, and verifies that every named import resolves to a "
        "real export in the target module. Catches the most common "
        "refactor failure mode without requiring a headless browser."
    )


def section_ops(doc):
    doc.add_heading("14. Operational Concerns", level=1)

    doc.add_heading("Backup and restore", level=2)
    add_code_block(doc, [
        "# Snapshot the database",
        "docker compose exec postgres pg_dump -U elite elite_dangerous \\",
        "    > backups/elite_$(date +%Y%m%d).sql",
        "",
        "# Restore on a fresh stack",
        "cat backups/elite_2026XXXX.sql | docker compose exec -T postgres \\",
        "    psql -U elite -d elite_dangerous",
    ])
    doc.add_paragraph(
        "The matview is included in the dump. The processed_logs ledger "
        "is too, so a restored DB knows what it has already loaded."
    )

    doc.add_heading("Upgrading the schema", level=2)
    doc.add_paragraph(
        "schema.sql is only applied to a fresh PostgreSQL data volume. "
        "On an existing database two pathways exist:"
    )
    bullets = [
        "Tables and indexes: drop the affected tables, then run docker compose run --rm elite-etl --rebuild. This is the destructive option but simplest.",
        "Materialised view: pick up automatically. ensure_jump_aggregates extracts only the matview block from schema.sql and CREATE-IF-NOT-EXISTS executes it on every load.",
    ]
    for b in bullets:
        doc.add_paragraph(b, style="List Bullet")

    doc.add_heading("Observability", level=2)
    rows = [
        ("docker compose logs -f elite-watcher", "Per-file parse output + connection errors."),
        ("docker compose logs -f elite-map",     "Uvicorn access log + any unhandled exceptions."),
        ("/api/health",                          "Cheap to poll from external monitoring."),
        ("docker compose ps",                    "Service health states. With the new healthcheck, elite-map shows healthy/unhealthy."),
    ]
    two_col_table(doc, "Surface", "Use", rows, col0_cm=6.5)

    doc.add_heading("Security posture", level=2)
    bullets = [
        "Secrets: .env is gitignored; .env.example is the template. POSTGRES_PASSWORD must be changed before any non-local deployment.",
        "PostgreSQL 5432 is exposed on the host by default. Comment the ports: block in docker-compose.yml if you don't use external DB tools.",
        "CORS: tighten ALLOWED_ORIGINS in production. Default '*' is convenient for local-only setups.",
        "Map server: read-only, no auth. Don't expose 8051 to the public internet without putting a reverse proxy with auth in front.",
        "No journal data ever leaves the host. Three.js is vendored locally, not loaded from a CDN.",
    ]
    for b in bullets:
        doc.add_paragraph(b, style="List Bullet")


def section_extension(doc):
    doc.add_heading("15. Extension Points", level=1)

    doc.add_heading("Adding a new journal event type", level=2)
    add_code_block(doc, [
        "# 1. Define a new table in schema.sql.",
        "# 2. Add a parser to etl.py:",
        "def parse_<your_event>(ev, src):",
        "    return {",
        '        "<your_table>": [{...}]',
        "    }",
        "",
        "# 3. Register it in EVENT_PARSERS:",
        '    "<YourEvent>": parse_<your_event>,',
        "",
        "# 4. Add the table name to SIMPLE_TABLES (if it doesn't need an upsert)",
        "#    or write a custom upsert_* function.",
        "",
        "# 5. Add tests in tests/test_parsers.py.",
        "",
        "# 6. Re-load: docker compose run --rm elite-etl --rebuild",
    ], lang_label="etl.py")

    doc.add_heading("Adding a new API endpoint", level=2)
    doc.add_paragraph(
        "Decorate a function with @app.get and return JSONResponse. Keep "
        "the connection lifecycle inside a try/finally — there is no "
        "pool. Existing endpoints are good templates."
    )

    doc.add_heading("Modernising the front-end", level=2)
    bullets = [
        "Three.js: switch from the UMD r128 build to three.module.r170+. One-line change in scene.js / jumps.js / panels.js / ship-viewer.js / main.js to `import * as THREE from '/static/vendor/three.module.js'` plus dropping the global <script> tag.",
        "Build pipeline: esbuild or Vite would let you split panels.js (the 557-line outlier) into bounty-panel.js, mining-panel.js, detail-panel.js without paying per-import network costs.",
        "Type checking: TypeScript could be added incrementally; state.js is a natural place for the first interface declaration.",
        "OrbitControls upgrade: pull the official OrbitControls module instead of the custom implementation. Adds inertia, touch support.",
    ]
    for b in bullets:
        doc.add_paragraph(b, style="List Bullet")

    doc.add_heading("Operational extensions", level=2)
    bullets = [
        "EDDN integration: parse the live galaxy-wide signal feed into the same schema for 'what's around me' queries.",
        "Multi-user: the schema is already FID-keyed; add HTTP basic-auth in front of FastAPI and a session->FID mapping.",
        "Materialised view incremental refresh: pg_ivm or a partition-on-source_file scheme would avoid the full rebuild.",
        "Prometheus metrics: a /metrics endpoint exposing query timings + watcher lag would round out the observability story.",
    ]
    for b in bullets:
        doc.add_paragraph(b, style="List Bullet")


def section_changelog(doc):
    doc.add_heading("16. Changelog (relative to imported baseline)", level=1)
    rows = [
        ("Hygiene",        ".gitignore at repo root; .env split into .env.example + gitignored .env."),
        ("Parser fixes",   "system_factions.id collision (FSDJump vs Location); FSSSignalDiscovered signal_type bug. Both regression-tested."),
        ("Watcher tidy",   "Removed lazy psycopg2_op_error() shim; top-level imports throughout."),
        ("Tests",          "19-test parser suite + elite-tests compose profile."),
        ("Performance",    "jump_aggregates materialised view + automatic refresh hooks. /api/jumps is now a single scan."),
        ("Health probe",   "/api/health endpoint + Docker healthcheck on elite-map."),
        ("CORS",           "Configurable via ALLOWED_ORIGINS."),
        ("Vendored deps",  "Three.js r128 served from /static/vendor/. No CDN."),
        ("CSS extraction", "map.css separated from map.html (547 → 0 inline lines)."),
        ("JS modularisation", "Inline 2,017-line <script> split into 9 ES modules under /static/js/."),
        ("Static checker", "tools/tests/check_imports.cjs — module graph cross-reference."),
        ("Docs",           "User Guide + this Technical Reference, both reproducible from python-docx generators in tools/."),
    ]
    two_col_table(doc, "Area", "Change", rows, col0_cm=4.0)


# ── main ───────────────────────────────────────────────────────

def main():
    out_dir = Path(__file__).resolve().parent.parent / "docs"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "EliteGalaxyMap-TechnicalReference.docx"

    doc = Document()
    configure_styles(doc)

    for s in doc.sections:
        s.top_margin    = Cm(2.0)
        s.bottom_margin = Cm(2.0)
        s.left_margin   = Cm(2.2)
        s.right_margin  = Cm(2.2)

    title_page(doc)
    section_intro(doc)
    section_architecture(doc)
    section_stack(doc)
    section_data_model(doc)
    section_etl(doc)
    section_watcher(doc)
    section_matview(doc)
    section_http_api(doc)
    section_frontend(doc)
    section_threejs(doc)
    section_performance(doc)
    section_build_deploy(doc)
    section_testing(doc)
    section_ops(doc)
    section_extension(doc)
    section_changelog(doc)

    doc.save(out_path)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
