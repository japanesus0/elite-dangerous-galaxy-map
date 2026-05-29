#!/usr/bin/env python3
"""
Build the Elite Dangerous Galaxy Map — User Guide as a .docx.

Run via docker so we don't need python-docx on the host:

    docker run --rm \
        -v "$(pwd):/work" -w /work \
        python:3.12-slim sh -c \
        "pip install -q python-docx==1.1.2 && python tools/build_user_guide.py"

Output: docs/EliteGalaxyMap-UserGuide.docx
"""

from pathlib import Path

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Pt, RGBColor, Inches, Cm


# ── styling helpers ────────────────────────────────────────────

ED_BLUE   = RGBColor(0x1A, 0x9F, 0xFF)
ED_AMBER  = RGBColor(0xFF, 0xAB, 0x00)
ED_DIM    = RGBColor(0x4A, 0x7A, 0x9B)
ED_DARK   = RGBColor(0x10, 0x18, 0x28)
ED_RED    = RGBColor(0xFF, 0x17, 0x44)
ED_GREEN  = RGBColor(0x00, 0xA8, 0x55)


def shade(cell, hex_no_hash):
    """Apply background shading to a table cell."""
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


def add_code_block(doc, lines):
    """Render a monospace code block with light-grey shading."""
    style = doc.styles["Normal"]
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Cm(0.5)
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after  = Pt(8)
    for i, line in enumerate(lines):
        if i:
            p.add_run().add_break()
        r = p.add_run(line)
        r.font.name  = "Consolas"
        r.font.size  = Pt(10)
        r.font.color.rgb = ED_DARK
    # shade the paragraph
    pPr = p._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), "f1f4f7")
    pPr.append(shd)


def configure_styles(doc):
    """Tune Normal + heading styles to be clean and readable."""
    base = doc.styles["Normal"]
    base.font.name = "Calibri"
    base.font.size = Pt(11)

    h1 = doc.styles["Heading 1"]
    h1.font.name = "Calibri"
    h1.font.size = Pt(20)
    h1.font.bold = True
    h1.font.color.rgb = ED_BLUE

    h2 = doc.styles["Heading 2"]
    h2.font.name = "Calibri"
    h2.font.size = Pt(15)
    h2.font.bold = True
    h2.font.color.rgb = ED_BLUE

    h3 = doc.styles["Heading 3"]
    h3.font.name = "Calibri"
    h3.font.size = Pt(12)
    h3.font.bold = True
    h3.font.color.rgb = ED_DIM


# ── content building blocks ────────────────────────────────────

def title_page(doc):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_run(p, "Elite Dangerous", bold=True, color=ED_BLUE,  size=28)
    p.add_run().add_break()
    add_run(p, "Galaxy Map",       bold=True, color=ED_AMBER, size=28)

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_run(sub, "User Guide", italic=True, color=ED_DIM, size=16)

    spacer = doc.add_paragraph()
    spacer.paragraph_format.space_before = Pt(40)

    desc = doc.add_paragraph()
    desc.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_run(desc,
            "Interactive 3D visualisation of your Frontier journal logs — "
            "every jump, every discovery, every bounty, replayed on a "
            "procedurally rendered Milky Way.",
            italic=True, color=ED_DIM, size=11)

    doc.add_paragraph()
    info = doc.add_paragraph()
    info.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_run(info, "Version 1.0  •  Self-hosted via Docker  •  Frontier Journal v40+",
            color=ED_DIM, size=10)

    doc.add_page_break()


def section_overview(doc):
    doc.add_heading("1. Overview", level=1)

    doc.add_paragraph(
        "Elite Dangerous Galaxy Map is a self-hosted web application that "
        "ingests your local Frontier Journal log files, loads them into a "
        "PostgreSQL database, and renders an interactive 3D galaxy map you "
        "can scrub through like a video timeline. It runs entirely on your "
        "own machine — no data leaves your computer."
    )

    doc.add_heading("What it shows you", level=2)
    bullets = [
        "Every star system you have visited, plotted on a procedural Milky Way.",
        "Per-jump enrichment: first discoveries, Earth-like worlds, bounties collected, materials gathered, missions, sessions and minerals refined.",
        "A scrubbable timeline so you can replay your career in chronological order.",
        "Aggregated combat and mining statistics, both lifetime and timeline-filtered.",
        "Per-system drill-down: every body scanned, every bounty collected, on the visit you click on.",
        "Live ship viewer that mirrors whichever ship you were flying at the cursor's moment in time.",
    ]
    for b in bullets:
        doc.add_paragraph(b, style="List Bullet")

    doc.add_heading("Who it is for", level=2)
    doc.add_paragraph(
        "Anyone who plays Elite Dangerous and wants to look back over their "
        "career in something richer than the in-game travel log. The setup "
        "is one Docker command; after that you drop your journal files into "
        "a folder and they load themselves."
    )


def section_system_requirements(doc):
    doc.add_heading("2. System Requirements", level=1)

    rows = [
        ("Operating System", "Windows, macOS or Linux. Tested on Windows 10/11."),
        ("Docker",           "Docker Desktop (or Docker Engine on Linux) with Docker Compose v2."),
        ("RAM",              "4 GB free is comfortable. The map renders fine on integrated graphics."),
        ("Disk",             "About 1 GB for the container images plus the size of your journal logs."),
        ("Browser",          "Any modern Chromium-based browser (Chrome, Edge, Brave) or Firefox 115+. WebGL support required."),
        ("Network",          "All services run on localhost. No internet connection required at runtime."),
    ]
    t = doc.add_table(rows=len(rows), cols=2)
    t.autofit = False
    t.columns[0].width = Cm(4.0)
    t.columns[1].width = Cm(12.0)
    for i, (k, v) in enumerate(rows):
        c0, c1 = t.rows[i].cells
        c0.width = Cm(4.0); c1.width = Cm(12.0)
        c0.text = ""; c1.text = ""
        add_run(c0.paragraphs[0], k, bold=True, color=ED_BLUE)
        c1.paragraphs[0].add_run(v)
        shade(c0, "eef4fa")
        for c in (c0, c1):
            set_cell_borders(c)
            c.vertical_alignment = WD_ALIGN_VERTICAL.TOP


def section_installation(doc):
    doc.add_heading("3. Installation and First Run", level=1)

    doc.add_paragraph(
        "The application ships as a Docker Compose stack with four services: "
        "PostgreSQL, the ETL loader, the journal watcher, and the map server. "
        "Setup is three steps."
    )

    doc.add_heading("Step 1 — Configure credentials", level=2)
    doc.add_paragraph(
        "Copy the example environment file and edit the database password. "
        "You only need to do this once."
    )
    add_code_block(doc, [
        "cd ed-map",
        "cp .env.example .env",
        "# open .env in any editor and change POSTGRES_PASSWORD",
    ])

    doc.add_heading("Step 2 — Start the stack", level=2)
    doc.add_paragraph(
        "From inside the ed-map folder, bring everything up. PostgreSQL "
        "initialises its schema on first boot; subsequent starts are fast."
    )
    add_code_block(doc, ["docker compose up -d"])
    doc.add_paragraph(
        "Wait roughly 15 seconds for PostgreSQL to report healthy. The "
        "watcher and map services will start automatically once it does."
    )

    doc.add_heading("Step 3 — Open the map", level=2)
    doc.add_paragraph(
        "Visit the following URL in your browser. The first load fetches "
        "your full jump history and may take a few seconds on a large database."
    )
    add_code_block(doc, ["http://localhost:8051/"])

    doc.add_heading("Verifying it's working", level=2)
    doc.add_paragraph(
        "Two quick checks confirm the stack is healthy:"
    )
    doc.add_paragraph(
        "Run docker compose ps. All four containers should be Up.",
        style="List Bullet")
    doc.add_paragraph(
        "Visit http://localhost:8051/api/health. You should see "
        "{\"status\":\"ok\",\"db\":\"ok\",\"matview\":\"ok\"}.",
        style="List Bullet")


def section_journal_logs(doc):
    doc.add_heading("4. Loading Your Journal Logs", level=1)

    doc.add_paragraph(
        "Frontier writes a new Journal log every time you start the game. "
        "On Windows these live at:"
    )
    add_code_block(doc, [r"%USERPROFILE%\Saved Games\Frontier Developments\Elite Dangerous"])

    doc.add_paragraph(
        "Drop any Journal*.log files you want to import into the JournalLogs "
        "folder next to the ed-map directory. The watcher service polls this "
        "folder every 30 seconds and will:"
    )
    for s in [
        "Parse new files and insert their events into PostgreSQL.",
        "Refresh the per-jump summary used by the map.",
        "Move processed files into JournalLogs/Loaded/ so they aren't picked up twice.",
    ]:
        doc.add_paragraph(s, style="List Bullet")

    doc.add_heading("Watching it work", level=2)
    add_code_block(doc, ["docker compose logs -f elite-watcher"])
    doc.add_paragraph(
        "You will see a line per file as it is parsed, with the event count "
        "and any parse errors. After loading, the map page will reflect the "
        "new data on its next refresh."
    )

    doc.add_heading("Bulk re-import", level=2)
    doc.add_paragraph(
        "If you ever want to drop the database and rebuild from scratch — "
        "for instance after a schema change — run:"
    )
    add_code_block(doc, ["docker compose run --rm elite-etl --rebuild"])
    doc.add_paragraph(
        "This drops every table, recreates the schema, and reloads every "
        "Journal*.log it can find under JournalLogs/ (recursively, including "
        "the Loaded/ subfolder)."
    )


def section_interface(doc):
    doc.add_heading("5. The Interface", level=1)

    doc.add_paragraph(
        "The map fills your browser window, with five fixed UI strips around "
        "the edges:"
    )
    items = [
        ("Top bar — Stats", "Live counters that follow the timeline cursor: jumps, light-years travelled, unique systems, discoveries, Earth-likes, bounties, credits, missions, sessions, materials and minerals."),
        ("Top-left — Legend", "Colour key for the dot types you'll see on the map."),
        ("Top-right — Controls", "Path visibility, dot size, playback speed, follow-cam, last-N filter, commander selector, and three log-panel buttons."),
        ("Bottom-left — Ship Viewer", "Wireframe silhouette of the ship you were flying at the cursor's moment, plus its name and ID."),
        ("Bottom-right — System Info", "Headline numbers for the currently selected jump: distance from Sol, security, population, discoveries."),
        ("Bottom — Timeline", "Play, step and reset controls plus a scrubber covering every jump in chronological order."),
    ]
    for title, desc in items:
        p = doc.add_paragraph(style="List Bullet")
        add_run(p, title + " — ", bold=True, color=ED_BLUE)
        p.add_run(desc)

    doc.add_heading("Camera controls", level=2)
    rows = [
        ("Left-click + drag",  "Orbit around the current target."),
        ("Right-click + drag", "Pan the view."),
        ("Mouse wheel",        "Zoom in / out."),
        ("Click a dot",        "Open the System Detail panel for that visit."),
        ("Hover a dot",        "Show a quick tooltip with system name, date and any enrichment."),
    ]
    t = doc.add_table(rows=len(rows) + 1, cols=2)
    t.autofit = False
    hdr0, hdr1 = t.rows[0].cells
    add_run(hdr0.paragraphs[0], "Action",  bold=True, color=ED_BLUE)
    add_run(hdr1.paragraphs[0], "Result",  bold=True, color=ED_BLUE)
    shade(hdr0, "eef4fa"); shade(hdr1, "eef4fa")
    set_cell_borders(hdr0); set_cell_borders(hdr1)
    for i, (act, res) in enumerate(rows, start=1):
        c0, c1 = t.rows[i].cells
        c0.text = act
        c1.text = res
        set_cell_borders(c0); set_cell_borders(c1)


def section_timeline(doc):
    doc.add_heading("6. Timeline and Playback", level=1)

    doc.add_paragraph(
        "The slider at the bottom of the screen represents every jump on "
        "your career timeline, from your earliest log forward. Moving it "
        "rewinds and fast-forwards the entire UI in one motion: stats bar, "
        "system info, ship viewer, panels and the active-jump halo all snap "
        "to the cursor position."
    )

    doc.add_heading("Controls", level=2)
    rows = [
        ("▶ PLAY / ⏸ PAUSE", "Auto-advance through the timeline at the selected speed."),
        ("⟳",                "Reset the cursor to the start of the timeline."),
        ("◀ / ▶",            "Step back / forward by exactly one jump."),
        ("Slider",           "Drag to scrub. Stops playback automatically."),
        ("Speed selector",   "0.25× to 100× of one jump per second. The 100× setting takes 5-jump strides."),
    ]
    t = doc.add_table(rows=len(rows) + 1, cols=2)
    hdr0, hdr1 = t.rows[0].cells
    add_run(hdr0.paragraphs[0], "Control", bold=True, color=ED_BLUE)
    add_run(hdr1.paragraphs[0], "Effect",  bold=True, color=ED_BLUE)
    shade(hdr0, "eef4fa"); shade(hdr1, "eef4fa")
    set_cell_borders(hdr0); set_cell_borders(hdr1)
    for i, (a, b) in enumerate(rows, start=1):
        c0, c1 = t.rows[i].cells
        c0.text, c1.text = a, b
        set_cell_borders(c0); set_cell_borders(c1)

    doc.add_heading("Follow camera", level=2)
    doc.add_paragraph(
        "When Follow cam is On (the default), the camera smoothly tracks the "
        "active jump as it moves. Turn it Off if you want to inspect a "
        "particular region of the galaxy without the camera moving on you."
    )

    doc.add_heading("Last-N filter", level=2)
    doc.add_paragraph(
        "Use the Last N jumps slider or numeric input to display only a "
        "trailing window of jumps relative to the cursor — useful for "
        "isolating, say, your last expedition. 0 means show everything."
    )


def section_panels(doc):
    doc.add_heading("7. Panels", level=1)

    doc.add_heading("System Detail (right side)", level=2)
    doc.add_paragraph(
        "Click any dot on the map to open this panel. It shows information "
        "scoped to that single visit: the jump itself, every body you "
        "scanned, every first discovery, every Earth-like world, and every "
        "bounty you earned between arriving and your next jump out. The "
        "drill-down ignores all activity from later visits."
    )

    doc.add_heading("Bounty Log (left side)", level=2)
    doc.add_paragraph(
        "Click ⚔ BOUNTY LOG in the controls panel. Shows aggregated combat "
        "stats up to the timeline cursor: ships destroyed, total credits, "
        "average per kill, breakdown by ship type and faction, year-by-year "
        "activity, and a top-10 most-valuable-kills list. As the cursor "
        "advances during playback the panel refreshes once per second."
    )

    doc.add_heading("Mining Log (right side)", level=2)
    doc.add_paragraph(
        "Click ⛏ MINING LOG. Mirror image of the bounty panel for refining "
        "events: total units refined, materials by type, year-by-year "
        "activity, and a list of the most recent refining events."
    )

    doc.add_heading("Bounty Activity Chart", level=2)
    doc.add_paragraph(
        "Click 📊 BOUNTY CHART. Shows a strip chart aligned to the timeline "
        "slider, with one bar per ~3 pixels of slider width. Bar height "
        "encodes the total bounty credits earned in that bucket of jumps "
        "(log-scaled so a single huge payout doesn't flatten everything "
        "else). The peak label tells you the value of the tallest bar."
    )


def section_commanders(doc):
    doc.add_heading("8. Multi-Commander Support", level=1)

    doc.add_paragraph(
        "If your journal logs span more than one commander FID, a Cmdr "
        "selector appears in the controls panel listing each commander "
        "with their jump count. Switching commanders triggers a fresh "
        "scene build filtered to that commander's logs only — including "
        "the stats bar, panels, and the ship viewer."
    )
    doc.add_paragraph(
        "If only one commander appears in your data, the selector stays "
        "hidden and the commander's name is shown in the top-left of the "
        "stats bar instead."
    )


def section_health(doc):
    doc.add_heading("9. Health Endpoint and Troubleshooting", level=1)

    doc.add_paragraph(
        "The map server exposes /api/health as a quick liveness probe. "
        "It returns three signals:"
    )
    rows = [
        ("ok",       "Database reachable and the per-jump summary view is populated. Everything works."),
        ("degraded", "Database is reachable but the jump_aggregates view hasn't been built yet. Run the ETL once: docker compose run --rm elite-etl"),
        ("down",     "Cannot reach PostgreSQL. Returns HTTP 503. Check docker compose ps and logs."),
    ]
    t = doc.add_table(rows=len(rows) + 1, cols=2)
    hdr0, hdr1 = t.rows[0].cells
    add_run(hdr0.paragraphs[0], "Status",   bold=True, color=ED_BLUE)
    add_run(hdr1.paragraphs[0], "Meaning",  bold=True, color=ED_BLUE)
    shade(hdr0, "eef4fa"); shade(hdr1, "eef4fa")
    set_cell_borders(hdr0); set_cell_borders(hdr1)
    for i, (a, b) in enumerate(rows, start=1):
        c0, c1 = t.rows[i].cells
        c0.text, c1.text = a, b
        set_cell_borders(c0); set_cell_borders(c1)

    doc.add_heading("Common issues", level=2)

    issues = [
        ("The page won't load at localhost:8051",
         "Check docker compose ps. If elite-map is restarting, look at the "
         "logs: docker compose logs elite-map."),
        ("/api/jumps returns a 503 with 'view not initialised'",
         "The materialised view that powers the map hasn't been created. "
         "Run docker compose run --rm elite-etl once and reload."),
        ("Map is empty / 0 jumps",
         "Either no logs have been loaded yet, or the watcher hasn't moved "
         "any files. Drop a Journal*.log into JournalLogs/ and watch with "
         "docker compose logs -f elite-watcher."),
        ("Wrong commander showing in stats bar",
         "Use the commander selector. If it's missing entirely your logs "
         "only contain one commander."),
        ("After upgrading, the matview SQL has changed",
         "Existing databases pick up matview changes lazily on the next "
         "ETL run. For schema (table) changes you need a full rebuild: "
         "docker compose run --rm elite-etl --rebuild."),
    ]
    for title, body in issues:
        p = doc.add_paragraph()
        add_run(p, title, bold=True, color=ED_RED)
        doc.add_paragraph(body)


def section_running_tests(doc):
    doc.add_heading("10. Running the Test Suite", level=1)
    doc.add_paragraph(
        "Nineteen unit tests cover the journal-log parsers and protect "
        "against regressions when the journal format shifts. They have no "
        "database dependency and finish in well under a second:"
    )
    add_code_block(doc, ["docker compose --profile test run --rm elite-tests"])


def section_appendix(doc):
    doc.add_heading("11. Appendix — Architecture at a Glance", level=1)

    doc.add_paragraph("Four containers running on a private Docker network:")
    services = [
        ("postgres",       "Stores everything. PostgreSQL 16, persisted to a Docker volume so your data survives restarts."),
        ("elite-watcher",  "Polls JournalLogs/ every 30 seconds, parses new files, refreshes the summary view, moves files to Loaded/."),
        ("elite-etl",      "Same parsing logic as the watcher, but as a one-shot CLI for bulk loads and full rebuilds."),
        ("elite-map",      "FastAPI server on port 8051 — serves the HTML map, the static JS modules, and the JSON API the map consumes."),
    ]
    for name, desc in services:
        p = doc.add_paragraph(style="List Bullet")
        add_run(p, name, bold=True, color=ED_BLUE)
        p.add_run(" — " + desc)

    doc.add_heading("HTTP API", level=2)
    rows = [
        ("GET /",                          "Serves map.html"),
        ("GET /static/...",                "JS modules, CSS, vendored Three.js"),
        ("GET /api/health",                "Liveness + DB readiness probe"),
        ("GET /api/jumps",                 "Every jump (with enrichment) for the timeline"),
        ("GET /api/jumps?commander=<fid>", "Same, filtered to one commander"),
        ("GET /api/system/<address>",      "Drill-down for a single system visit"),
        ("GET /api/stats",                 "Lifetime totals for the stats bar"),
        ("GET /api/commanders",            "All commanders found in the logs"),
        ("GET /api/loadouts",              "All loadout records (powers the ship viewer)"),
        ("GET /api/bounties/summary",      "Aggregated combat panel data"),
        ("GET /api/mining/summary",        "Aggregated mining panel data"),
    ]
    t = doc.add_table(rows=len(rows) + 1, cols=2)
    hdr0, hdr1 = t.rows[0].cells
    add_run(hdr0.paragraphs[0], "Endpoint",    bold=True, color=ED_BLUE)
    add_run(hdr1.paragraphs[0], "Description", bold=True, color=ED_BLUE)
    shade(hdr0, "eef4fa"); shade(hdr1, "eef4fa")
    set_cell_borders(hdr0); set_cell_borders(hdr1)
    for i, (a, b) in enumerate(rows, start=1):
        c0, c1 = t.rows[i].cells
        c0.text = ""; c1.text = ""
        add_run(c0.paragraphs[0], a, font="Consolas", size=10, color=ED_DARK)
        c1.paragraphs[0].add_run(b)
        set_cell_borders(c0); set_cell_borders(c1)

    doc.add_heading("Privacy", level=2)
    doc.add_paragraph(
        "Everything runs locally. Your journal logs, the database, the map "
        "server and your browser only ever talk over localhost. No data is "
        "sent to any external service at any time."
    )


def section_glossary(doc):
    doc.add_heading("12. Glossary", level=1)
    items = [
        ("FID",              "Frontier ID — a stable per-commander identifier in the journal logs."),
        ("FSDJump",          "The journal event written every time you complete a hyperspace jump. Drives every dot on the map."),
        ("First discovery",  "A body you were the first commander to scan. Coloured green on the map."),
        ("Earth-like world", "A planet with the PlanetClass 'Earthlike body'. Coloured cyan."),
        ("Bounty",           "Combat reward earned for destroying a wanted ship. Coloured red."),
        ("System address",   "Frontier's unique 64-bit identifier for a star system. Stable across all commanders."),
        ("Materialised view", "A precomputed query result kept in PostgreSQL. The map uses one (jump_aggregates) so /api/jumps returns instantly."),
    ]
    for term, defn in items:
        p = doc.add_paragraph()
        add_run(p, term, bold=True, color=ED_BLUE)
        p.add_run(" — " + defn)


# ── main ───────────────────────────────────────────────────────

def main():
    out_dir = Path(__file__).resolve().parent.parent / "docs"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "EliteGalaxyMap-UserGuide.docx"

    doc = Document()
    configure_styles(doc)

    # Page margins — slightly narrower than the Word default for a denser look
    for s in doc.sections:
        s.top_margin    = Cm(2.0)
        s.bottom_margin = Cm(2.0)
        s.left_margin   = Cm(2.2)
        s.right_margin  = Cm(2.2)

    title_page(doc)
    section_overview(doc)
    section_system_requirements(doc)
    section_installation(doc)
    section_journal_logs(doc)
    section_interface(doc)
    section_timeline(doc)
    section_panels(doc)
    section_commanders(doc)
    section_health(doc)
    section_running_tests(doc)
    section_appendix(doc)
    section_glossary(doc)

    doc.save(out_path)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
