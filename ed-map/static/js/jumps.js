// ═══════════════════════════════════════════════════════════════
// jumps.js — jump-point cloud + path line + active-jump halo
//            + prefix-sum index for O(1) live stats updates
// ═══════════════════════════════════════════════════════════════

import { COLOR } from './constants.js';
import { state } from './state.js';
import { scene, glowTex } from './scene.js';

// ── Jump colour by enrichment fields ────────────────────────────

export function jumpColor(j) {
  const hasDisc   = j.first_discoveries  > 0;
  const hasEL     = j.earth_likes        > 0;
  const hasBounty = j.bounties_collected > 0;
  if (hasEL)                  return COLOR.earthlike;
  if (hasDisc && hasBounty)   return COLOR.mixed;
  if (hasDisc)                return COLOR.discovery;
  if (hasBounty)              return COLOR.bounty;
  return COLOR.transit;
}


// ── Active-jump halo (single amber glow anchored to the current point) ──
// Two materials layered so the halo stays readable at any zoom:
//   - worldHaloMat: large, size-attenuated — dominant at mid/far zooms
//   - screenHaloMat: small, non-attenuated — a floor so very close zooms
//     never lose the marker entirely

export const activeHaloGeo = new THREE.BufferGeometry();
activeHaloGeo.setAttribute('position', new THREE.BufferAttribute(new Float32Array([0,0,0]), 3));

export const activeHaloMat = new THREE.PointsMaterial({
  color: COLOR.mixed,    // amber — same as "Discovery + Combat" legend entry
  size: 32,
  map: glowTex,
  sizeAttenuation: true,
  depthWrite: false,
  transparent: true,
  opacity: 0.85,
  alphaTest: 0.01,
});
const activeHaloScreenMat = new THREE.PointsMaterial({
  color: COLOR.mixed,
  size: 14,
  map: glowTex,
  sizeAttenuation: false,   // stays a readable pixel size regardless of zoom
  depthWrite: false,
  transparent: true,
  opacity: 0.9,
  alphaTest: 0.01,
});


// ── Build/replace the points + path scene objects from a jumps array ──

export function buildJumpScene(jumps) {
  if (state.pointsMesh)       { scene.remove(state.pointsMesh);       state.pointsMesh.geometry.dispose(); }
  if (state.pathLine)         { scene.remove(state.pathLine);         state.pathLine.geometry.dispose();   }
  if (state.activeHalo)       { scene.remove(state.activeHalo);       state.activeHalo       = null;       }
  if (state.activeHaloScreen) { scene.remove(state.activeHaloScreen); state.activeHaloScreen = null;       }

  const N = jumps.length;
  if (N === 0) return;

  const pos = new Float32Array(N * 3);
  const col = new Float32Array(N * 3);

  jumps.forEach((j, i) => {
    pos[i*3]   = j.x;
    pos[i*3+1] = j.y;
    pos[i*3+2] = j.z;
    const c = new THREE.Color(jumpColor(j));
    col[i*3] = c.r; col[i*3+1] = c.g; col[i*3+2] = c.b;
  });

  // ── Points ──
  state.pointsGeo = new THREE.BufferGeometry();
  state.pointsGeo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  state.pointsGeo.setAttribute('color',    new THREE.BufferAttribute(col, 3));
  state.pointsGeo.setDrawRange(0, state.currentIdx + 1);

  const pointsMat = new THREE.PointsMaterial({
    size: parseFloat(document.getElementById('range-size').value),
    vertexColors: true,
    sizeAttenuation: false,
    transparent: true,
    opacity: 0.9,
    depthWrite: false,
  });
  state.pointsMesh = new THREE.Points(state.pointsGeo, pointsMat);
  scene.add(state.pointsMesh);

  // ── Path line ──
  state.pathGeo = new THREE.BufferGeometry();
  state.pathGeo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  state.pathGeo.setDrawRange(0, state.currentIdx + 1);

  const pathMat = new THREE.LineBasicMaterial({
    color: 0x1e4a8a, transparent: true, opacity: 0.35, depthWrite: false,
  });
  state.pathLine = new THREE.Line(state.pathGeo, pathMat);
  state.pathLine.visible = document.getElementById('sel-path').value === '1';
  scene.add(state.pathLine);

  // ── Active-jump halo (amber glow on whichever dot is current) ──
  state.activeHalo = new THREE.Points(activeHaloGeo, activeHaloMat);
  state.activeHalo.renderOrder = 2;  // drawn after regular points so it's never occluded by them
  scene.add(state.activeHalo);
  // Screen-space floor halo — keeps the marker visible at any zoom
  state.activeHaloScreen = new THREE.Points(activeHaloGeo, activeHaloScreenMat);
  state.activeHaloScreen.renderOrder = 3;
  scene.add(state.activeHaloScreen);

  updateActiveMarker();
}


// ── Move the halo to the current jump's world coords + refresh label text ──

export function updateActiveMarker() {
  const j = state.jumpsData[state.currentIdx];
  if (!j) return;
  const p = activeHaloGeo.attributes.position.array;
  p[0] = j.x; p[1] = j.y; p[2] = j.z;
  activeHaloGeo.attributes.position.needsUpdate = true;
  activeHaloGeo.computeBoundingSphere();

  // Label text — system always available; ship info comes from /api/loadouts
  const sys = state.currentShipInfo;
  document.getElementById('ajl-system').textContent = j.star_system || '—';
  document.getElementById('ajl-ship').textContent   = sys.display || '—';
  document.getElementById('ajl-ident').textContent  =
    sys.ident ? ` · ${sys.ident}` :
    sys.name  ? ` · ${sys.name}`  : '';
}


// ── Prefix-sum scaffolding for O(1) updateLiveStats ──────────────
// Each array has length jumpsData.length + 1, with prefix[0] = 0 and
// prefix[k] = sum of field values from jumps 0..k-1. Cumulative to
// index `idx` is prefix[idx+1].
// systemsAtIdx[k] is the count of DISTINCT star_systems in jumps 0..k.

export function buildLiveStatsIndex() {
  const N  = state.jumpsData.length;
  const px = state.prefix;
  px.ly        = new Float64Array(N + 1);
  px.disc      = new Uint32Array (N + 1);
  px.el        = new Uint32Array (N + 1);
  px.bounties  = new Uint32Array (N + 1);
  px.credits   = new Float64Array(N + 1);   // can exceed 2^32
  px.materials = new Float64Array(N + 1);
  px.missions  = new Uint32Array (N + 1);
  px.sessions  = new Uint32Array (N + 1);
  px.minerals  = new Uint32Array (N + 1);
  px.systemsAtIdx = new Uint32Array(N);

  const seen = new Set();
  for (let i = 0; i < N; i++) {
    const j = state.jumpsData[i];
    px.ly       [i+1] = px.ly       [i] + (j.jump_dist           || 0);
    px.disc     [i+1] = px.disc     [i] + (j.first_discoveries   || 0);
    px.el       [i+1] = px.el       [i] + (j.earth_likes         || 0);
    px.bounties [i+1] = px.bounties [i] + (j.bounties_collected  || 0);
    px.credits  [i+1] = px.credits  [i] + (j.bounty_credits      || 0);
    px.materials[i+1] = px.materials[i] + (j.materials_collected || 0);
    px.missions [i+1] = px.missions [i] + (j.missions            || 0);
    px.sessions [i+1] = px.sessions [i] + (j.sessions            || 0);
    px.minerals [i+1] = px.minerals [i] + (j.minerals_mined      || 0);
    if (j.star_system) seen.add(j.star_system);
    px.systemsAtIdx[i] = seen.size;
  }
}


// ── Live stats bar update — pulls cumulative values from prefix arrays ──

import { fmtK } from './constants.js';

export function updateLiveStats(idx) {
  if (!state.jumpsData.length || !state.prefix.ly) return;
  const k  = idx + 1;   // prefix arrays are 1-indexed
  const px = state.prefix;
  document.getElementById('s-jumps').textContent     = k.toLocaleString();
  document.getElementById('s-ly').textContent        = fmtK(px.ly[k]) + ' LY';
  document.getElementById('s-systems').textContent   = (px.systemsAtIdx[idx] || 0).toLocaleString();
  document.getElementById('s-disc').textContent      = px.disc[k].toLocaleString();
  document.getElementById('s-el').textContent        = px.el[k].toLocaleString();
  document.getElementById('s-bounties').textContent  = px.bounties[k].toLocaleString();
  document.getElementById('s-credits').textContent   = fmtK(px.credits[k]);
  document.getElementById('s-materials').textContent = fmtK(px.materials[k]);
  document.getElementById('s-missions').textContent  = px.missions[k].toLocaleString();
  document.getElementById('s-sessions').textContent  = px.sessions[k].toLocaleString();
  document.getElementById('s-minerals').textContent  = fmtK(px.minerals[k]);
}
