// ═══════════════════════════════════════════════════════════════
// ship-viewer.js — wireframe ship-silhouette mini-scene + the
//                  client-side loadout binary search that keeps the
//                  current ship in sync with the timeline cursor.
// ═══════════════════════════════════════════════════════════════

import { SHIP_DISPLAY_NAMES } from './constants.js';
import { state } from './state.js';
import { updateActiveMarker } from './jumps.js';

// ── Ship sub-scene (rendered into a scissor inset by main.js animate) ──

export const shipScene  = new THREE.Scene();
export const shipCamera = new THREE.PerspectiveCamera(35, 210 / 180, 0.01, 100);
shipCamera.position.set(2.2, 0.9, 2.0);
shipCamera.lookAt(0, 0, 0);

const _shipLight = new THREE.DirectionalLight(0x88bbff, 0.4);
_shipLight.position.set(1, 2, 1);
shipScene.add(_shipLight);


// ── Mesh builder: a few small _box() primitives per ship ──

const _SHIP_MAT = new THREE.LineBasicMaterial({
  color: 0x1a9fff, transparent: true, opacity: 0.88,
});

function _box(w, h, d, x = 0, y = 0, z = 0) {
  const geo = new THREE.EdgesGeometry(new THREE.BoxGeometry(w, h, d));
  const ls  = new THREE.LineSegments(geo, _SHIP_MAT);
  ls.position.set(x, y, z);
  return ls;
}

function buildShipMesh(key) {
  const k = (key || '').toLowerCase();
  const g = new THREE.Group();

  if (k.includes('anaconda')) {
    g.add(_box(1.2,  0.40, 2.2));
    g.add(_box(2.6,  0.12, 1.2,  0,     -0.05,  0.2));
    g.add(_box(0.35, 0.38, 0.6,  0.8,   0,      0.7));
    g.add(_box(0.35, 0.38, 0.6, -0.8,   0,      0.7));
    g.add(_box(0.30, 0.30, 0.5,  0.4,   0.28,   0.6));
    g.add(_box(0.30, 0.30, 0.5, -0.4,   0.28,   0.6));
    g.add(_box(0.52, 0.32, 0.48, 0,     0.18,  -0.85));
  } else if (k.includes('python')) {
    g.add(_box(0.95, 0.32, 1.8));
    g.add(_box(2.2,  0.12, 1.0,  0,    -0.08,   0.1));
    g.add(_box(0.30, 0.32, 0.5,  0.7,   0,      0.65));
    g.add(_box(0.30, 0.32, 0.5, -0.7,   0,      0.65));
    g.add(_box(0.48, 0.28, 0.4,  0,     0.14,  -0.58));
  } else if (k.includes('federation_corvette') || k === 'corvette') {
    g.add(_box(1.2,  0.42, 2.4));
    g.add(_box(3.0,  0.15, 1.2,  0,    -0.10,   0.2));
    g.add(_box(0.40, 0.42, 0.7,  0.9,   0,      0.85));
    g.add(_box(0.40, 0.42, 0.7, -0.9,   0,      0.85));
    g.add(_box(0.55, 0.36, 0.5,  0,     0.20,  -0.90));
  } else if (k === 'cutter' || k.includes('imperial_cutter')) {
    g.add(_box(1.8,  0.32, 2.0));
    g.add(_box(3.0,  0.10, 1.2,  0,    -0.08,   0.1));
    g.add(_box(0.35, 0.32, 0.5,  0.7,   0,      0.8));
    g.add(_box(0.35, 0.32, 0.5, -0.7,   0,      0.8));
    g.add(_box(0.60, 0.30, 0.42, 0,     0.20,  -0.70));
    g.add(_box(1.0,  0.12, 0.6,  0,     0.22,   0.3));
  } else if (k === 'type10' || k.includes('type9_military')) {
    g.add(_box(1.4,  0.70, 2.2));
    g.add(_box(3.2,  0.20, 1.2,  0,     0,      0.1));
    g.add(_box(0.40, 0.50, 0.7,  1.0,   0,      0.7));
    g.add(_box(0.40, 0.50, 0.7, -1.0,   0,      0.7));
    g.add(_box(0.50, 0.50, 0.45, 0.3,   0.5,   -0.8));
    g.add(_box(0.45, 0.25, 0.6,  0,    -0.35,   0.8));
  } else if (k === 'type9') {
    g.add(_box(1.3,  0.75, 2.2));
    g.add(_box(2.0,  0.28, 1.0,  0,    -0.22,   0.1));
    g.add(_box(0.40, 0.48, 0.65, 0.75,  0,      0.75));
    g.add(_box(0.40, 0.48, 0.65,-0.75,  0,      0.75));
    g.add(_box(0.50, 0.48, 0.42, 0.3,   0.5,   -0.78));
  } else if (k === 'type7') {
    g.add(_box(1.0,  0.55, 1.9));
    g.add(_box(0.35, 0.40, 0.6,  0.55,  0,      0.65));
    g.add(_box(0.35, 0.40, 0.6, -0.55,  0,      0.65));
    g.add(_box(0.45, 0.40, 0.4,  0.2,   0.38,  -0.70));
  } else if (k === 'type6') {
    g.add(_box(0.85, 0.45, 1.7));
    g.add(_box(0.30, 0.35, 0.5,  0.45,  0,      0.6));
    g.add(_box(0.30, 0.35, 0.5, -0.45,  0,      0.6));
    g.add(_box(0.38, 0.35, 0.38, 0.12,  0.3,   -0.60));
  } else if (k === 'krait_mkii') {
    g.add(_box(0.90, 0.25, 1.6));
    g.add(_box(2.2,  0.10, 0.85, 0,    -0.05,   0.15));
    g.add(_box(0.30, 0.25, 0.48, 0.7,   0,      0.55));
    g.add(_box(0.30, 0.25, 0.48,-0.7,   0,      0.55));
    g.add(_box(0.55, 0.22, 0.45, 0,     0.10,  -0.45));
  } else if (k.includes('krait')) {
    // Krait Phantom — sleeker
    g.add(_box(0.80, 0.22, 1.5));
    g.add(_box(2.0,  0.09, 0.75, 0,    -0.04,   0.15));
    g.add(_box(0.28, 0.22, 0.45, 0.65,  0,      0.50));
    g.add(_box(0.28, 0.22, 0.45,-0.65,  0,      0.50));
    g.add(_box(0.48, 0.20, 0.40, 0,     0.09,  -0.42));
  } else if (k === 'asp_scout' || k.includes('asp_scout')) {
    g.add(_box(0.75, 0.28, 1.3));
    g.add(_box(1.9,  0.10, 0.85, 0,     0,      0.1));
    g.add(_box(0.28, 0.28, 0.45, 0.55,  0,      0.5));
    g.add(_box(0.28, 0.28, 0.45,-0.55,  0,      0.5));
    g.add(_box(0.42, 0.26, 0.40, 0,     0.10,  -0.42));
  } else if (k === 'asp' || k.includes('asp_explorer') ||
             (k.includes('asp') && !k.includes('scout'))) {
    g.add(_box(0.82, 0.30, 1.55));
    g.add(_box(2.1,  0.10, 0.92, 0,     0,      0.1));
    g.add(_box(0.30, 0.30, 0.48, 0.65,  0,      0.52));
    g.add(_box(0.30, 0.30, 0.48,-0.65,  0,      0.52));
    g.add(_box(0.45, 0.28, 0.44, 0,     0.12,  -0.50));
  } else if (k.includes('cobra_mkiv')) {
    g.add(_box(0.75, 0.26, 1.4));
    g.add(_box(1.85, 0.10, 0.75, 0,     0,      0.1));
    g.add(_box(0.40, 0.22, 0.40, 0,     0.10,  -0.42));
  } else if (k.includes('cobra')) {
    // Cobra Mk III — classic wide triangle
    g.add(_box(0.72, 0.24, 1.4));
    g.add(_box(2.0,  0.10, 0.82, 0,    -0.04,   0.15));
    g.add(_box(0.38, 0.22, 0.38, 0,     0.10,  -0.45));
  } else if (k.includes('alliance_chieftain') || k === 'chieftain') {
    g.add(_box(0.85, 0.28, 1.5));
    g.add(_box(1.9,  0.10, 0.80, 0,     0,      0.1));
    g.add(_box(0.30, 0.28, 0.45, 0.65,  0,      0.5));
    g.add(_box(0.30, 0.28, 0.45,-0.65,  0,      0.5));
    g.add(_box(0.50, 0.26, 0.40, 0,     0.12,  -0.45));
  } else if (k.includes('alliance')) {
    g.add(_box(0.80, 0.26, 1.45));
    g.add(_box(1.85, 0.10, 0.78, 0,     0,      0.1));
    g.add(_box(0.28, 0.26, 0.44, 0.60,  0,      0.48));
    g.add(_box(0.28, 0.26, 0.44,-0.60,  0,      0.48));
    g.add(_box(0.45, 0.24, 0.38, 0,     0.10,  -0.44));
  } else if (k.includes('mamba')) {
    g.add(_box(0.72, 0.20, 1.45));
    g.add(_box(2.2,  0.08, 0.78, 0,    -0.04,   0.12));
    g.add(_box(0.35, 0.18, 0.35, 0,     0.08,  -0.50));
  } else if (k.includes('ferdelance') || k.includes('fer_de_lance')) {
    g.add(_box(0.70, 0.20, 1.42));
    g.add(_box(2.15, 0.09, 0.80, 0,    -0.04,   0.12));
    g.add(_box(0.32, 0.18, 0.32, 0,     0.08,  -0.50));
  } else if (k.includes('vulture')) {
    g.add(_box(0.72, 0.28, 1.1));
    g.add(_box(1.55, 0.10, 0.72, 0,     0,      0.1));
    g.add(_box(0.58, 0.18, 0.50, 0,     0.18,   0.0));
    g.add(_box(0.38, 0.28, 0.30, 0,     0.10,  -0.28));
  } else if (k.includes('diamondbackscout')) {
    g.add(_box(0.65, 0.20, 1.1));
    g.add(_box(1.60, 0.08, 0.70, 0,    -0.04,   0.1));
    g.add(_box(0.32, 0.20, 0.30, 0,     0.09,  -0.35));
  } else if (k.includes('diamondback')) {
    g.add(_box(0.75, 0.22, 1.3));
    g.add(_box(1.85, 0.09, 0.78, 0,    -0.04,   0.1));
    g.add(_box(0.38, 0.22, 0.35, 0,     0.10,  -0.42));
  } else if (k.includes('federation_gunship') || k === 'gunship') {
    g.add(_box(1.05, 0.40, 1.55));
    g.add(_box(2.1,  0.15, 0.92, 0,    -0.10,   0.1));
    g.add(_box(0.35, 0.40, 0.52, 0.78,  0,      0.55));
    g.add(_box(0.35, 0.40, 0.52,-0.78,  0,      0.55));
    g.add(_box(0.50, 0.32, 0.44, 0,     0.16,  -0.50));
  } else if (k.includes('federation_dropship') || k === 'dropship') {
    g.add(_box(1.0,  0.38, 1.5));
    g.add(_box(2.0,  0.15, 0.90, 0,    -0.10,   0.1));
    g.add(_box(0.35, 0.38, 0.50, 0.75,  0,      0.55));
    g.add(_box(0.35, 0.38, 0.50,-0.75,  0,      0.55));
    g.add(_box(0.48, 0.30, 0.42, 0,     0.15,  -0.50));
  } else if (k === 'imperial_eagle' || k.includes('imp_eagle')) {
    g.add(_box(0.58, 0.14, 0.98));
    g.add(_box(1.55, 0.07, 0.65, 0,    -0.02,   0.08));
    g.add(_box(0.24, 0.16, 0.24, 0,     0.06,  -0.30));
  } else if (k.includes('eagle')) {
    g.add(_box(0.62, 0.15, 1.0));
    g.add(_box(1.65, 0.08, 0.68, 0,    -0.02,   0.1));
    g.add(_box(0.26, 0.18, 0.26, 0,     0.07,  -0.32));
  } else if (k.includes('viper_mkiv')) {
    g.add(_box(0.65, 0.20, 1.05));
    g.add(_box(1.45, 0.09, 0.65, 0,    -0.02,   0.08));
    g.add(_box(0.32, 0.18, 0.32, 0,     0.08,  -0.30));
  } else if (k.includes('viper')) {
    g.add(_box(0.62, 0.18, 1.02));
    g.add(_box(1.40, 0.08, 0.62, 0,    -0.02,   0.08));
    g.add(_box(0.30, 0.16, 0.30, 0,     0.08,  -0.28));
  } else if (k.includes('hauler')) {
    g.add(_box(0.70, 0.35, 1.0));
    g.add(_box(0.28, 0.30, 0.42, 0.38,  0,      0.4));
    g.add(_box(0.28, 0.30, 0.42,-0.38,  0,      0.4));
    g.add(_box(0.38, 0.28, 0.38, 0,     0.12,  -0.30));
  } else if (k.includes('adder')) {
    g.add(_box(0.75, 0.25, 1.15));
    g.add(_box(1.50, 0.10, 0.65, 0,     0,      0.1));
    g.add(_box(0.36, 0.22, 0.36, 0,     0.10,  -0.32));
  } else if (k.includes('beluga')) {
    g.add(_box(1.4,  0.60, 2.2));
    g.add(_box(2.6,  0.15, 0.90, 0,    -0.15,  -0.2));
    g.add(_box(0.50, 0.55, 0.50, 0,     0.15,  -0.85));
    g.add(_box(0.40, 0.38, 0.60, 0.7,   0,      0.7));
    g.add(_box(0.40, 0.38, 0.60,-0.7,   0,      0.7));
  } else if (k.includes('orca')) {
    g.add(_box(1.0,  0.45, 1.8));
    g.add(_box(2.2,  0.12, 0.85, 0,    -0.12,  -0.1));
    g.add(_box(0.45, 0.40, 0.50, 0,     0.15,  -0.60));
    g.add(_box(0.35, 0.32, 0.52, 0.62,  0,      0.62));
    g.add(_box(0.35, 0.32, 0.52,-0.62,  0,      0.62));
  } else if (k.includes('dolphin')) {
    g.add(_box(0.75, 0.35, 1.45));
    g.add(_box(1.70, 0.10, 0.70, 0,    -0.08,  -0.05));
    g.add(_box(0.38, 0.32, 0.38, 0,     0.12,  -0.50));
    g.add(_box(0.30, 0.28, 0.48, 0.50,  0,      0.5));
    g.add(_box(0.30, 0.28, 0.48,-0.50,  0,      0.5));
  } else if (k.includes('sidewinder')) {
    g.add(_box(0.80, 0.15, 1.2));
    g.add(_box(1.80, 0.08, 0.60, 0,     0,      0.2));
    g.add(_box(0.30, 0.18, 0.30, 0,     0.05,  -0.30));
  } else {
    // Fallback — generic medium ship silhouette
    g.add(_box(0.75, 0.25, 1.3));
    g.add(_box(1.80, 0.10, 0.70, 0,    -0.04,   0.1));
    g.add(_box(0.35, 0.22, 0.38, 0,     0.10,  -0.42));
  }

  // Normalise so the ship fits in a ±0.85 bounding sphere
  const box3  = new THREE.Box3().setFromObject(g);
  const sz    = new THREE.Vector3();
  box3.getSize(sz);
  const scale = 1.7 / Math.max(sz.x, sz.y, sz.z);
  g.scale.setScalar(scale);
  // Recenter after scale
  const ctr = new THREE.Vector3();
  new THREE.Box3().setFromObject(g).getCenter(ctr);
  g.position.sub(ctr);

  return g;
}


// ── Mounting / replacing the active ship mesh ──

export let shipMeshGroup = null;
let _lastShipKey  = null;
let _lastLoadoutIdx = -1;

function setShipMesh(shipKey) {
  if (shipMeshGroup) {
    shipScene.remove(shipMeshGroup);
    shipMeshGroup.traverse(o => { if (o.geometry) o.geometry.dispose(); });
    shipMeshGroup = null;
  }
  if (!shipKey) return;
  shipMeshGroup = buildShipMesh(shipKey);
  shipScene.add(shipMeshGroup);
}


// ── Loadout binary search (replaces per-tick /api/ship calls) ──

export async function preloadLoadouts() {
  try {
    state.loadoutsData = await fetch('/api/loadouts').then(r => r.json());
  } catch (_) {
    state.loadoutsData = [];
  }
}

// Find the last loadout with timestamp <= target. Binary search, O(log n).
function _resolveLoadoutIdx(ts) {
  const data = state.loadoutsData;
  if (!data.length) return -1;
  let lo = 0, hi = data.length - 1, ans = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (data[mid].timestamp <= ts) { ans = mid; lo = mid + 1; }
    else                           { hi = mid - 1; }
  }
  return ans;
}

export function resolveShipAt(timestamp) {
  if (!timestamp) return;
  const idx = _resolveLoadoutIdx(timestamp);
  if (idx === -1) return;
  if (idx === _lastLoadoutIdx) return;   // no change → skip DOM thrash
  _lastLoadoutIdx = idx;

  const row = state.loadoutsData[idx];
  const key = (row.ship || '').toLowerCase();
  if (key !== _lastShipKey) {
    _lastShipKey = key;
    setShipMesh(key);
  }
  const displayName = SHIP_DISPLAY_NAMES[key] || row.ship || '—';
  const ident       = [row.ship_name, row.ship_ident].filter(Boolean).join(' · ');
  document.getElementById('ship-viewer-name').textContent  = displayName;
  document.getElementById('ship-viewer-ident').textContent = ident;

  state.currentShipInfo = {
    display: displayName,
    ident:   row.ship_ident || '',
    name:    row.ship_name  || '',
  };
  updateActiveMarker();
}

// Reset the cache so the next resolveShipAt is forced to re-render
// (used after a commander switch loads a different loadouts list).
export function resetShipResolverCache() {
  _lastLoadoutIdx = -1;
}

// Convenience: pull current jump's timestamp and resolve. Used after
// playback stops, where we want to make sure the ship matches the
// stopped-on position even if the play loop missed an update.
export function snapShipToCurrent() {
  if (!state.jumpsData.length) return;
  const j = state.jumpsData[state.currentIdx];
  if (j) resolveShipAt(j.timestamp);
}
