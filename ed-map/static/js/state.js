// ═══════════════════════════════════════════════════════════════
// state.js — shared mutable state across modules
// ───────────────────────────────────────────────────────────────
// Every importer gets the SAME object reference, so writes from one
// module are immediately visible to all others. This is the simplest
// way to preserve the original "shared globals" model while still
// splitting code into multiple files. Keep this file dependency-free.
// ═══════════════════════════════════════════════════════════════

export const state = {
  // ── Data loaded from /api ──
  jumpsData:    [],   // array of jump rows from /api/jumps
  loadoutsData: [],   // array of loadout rows from /api/loadouts (sorted by ts)

  // ── Timeline / playback ──
  currentIdx:       0,
  isPlaying:        false,
  playInterval:     null,
  followMode:       true,
  lastNJumps:       0,        // 0 = show all; >0 = trailing window
  currentCommander: null,     // null | string fid

  // ── Scene refs (assigned by jumps.js / scene.js) ──
  pointsMesh:       null,
  pointsGeo:        null,
  pathLine:         null,
  pathGeo:          null,
  activeHalo:       null,
  activeHaloScreen: null,

  // ── Ship / label info ──
  currentShipInfo: { display: '', ident: '', name: '' },

  // ── Cached prefix-sum arrays for O(1) live stats ──
  prefix: {
    ly: null, disc: null, el: null, bounties: null, credits: null,
    materials: null, missions: null, sessions: null, minerals: null,
    systemsAtIdx: null,
  },
};
