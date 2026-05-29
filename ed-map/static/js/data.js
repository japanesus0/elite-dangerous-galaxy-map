// ═══════════════════════════════════════════════════════════════
// data.js — initial load + commander reload + stats bar update.
//           This module owns the lifecycle: fetch from /api,
//           hand off to jumps.js / timeline.js / ship-viewer.js.
// ═══════════════════════════════════════════════════════════════

import { fmtK } from './constants.js';
import { state } from './state.js';
import { orbit } from './scene.js';
import { buildJumpScene, buildLiveStatsIndex, updateLiveStats } from './jumps.js';
import {
  setIndex, slider, tlDate, tlProgress,
  buildBountyChart, bountyChartVisible, stopPlay,
} from './timeline.js';
import { updateSystemInfo } from './panels.js';
import { preloadLoadouts, resolveShipAt, resetShipResolverCache } from './ship-viewer.js';

const followTarget = new THREE.Vector3();   // local to this module — main.js reads via export


// ── Loading screen helper ───────────────────────────────────────

function setLoading(pct, msg) {
  document.getElementById('loading-bar').style.width    = pct + '%';
  document.getElementById('loading-status').textContent = msg;
}


// ── Stats bar (initial total counts, before the prefix-sum view kicks in) ──

function updateStats(s) {
  const fmt = n => Number(n).toLocaleString();
  document.getElementById('s-jumps').textContent     = fmt(s.total_jumps);
  document.getElementById('s-ly').textContent        = fmtK(Math.round(s.total_ly)) + ' LY';
  document.getElementById('s-systems').textContent   = fmt(s.unique_systems);
  document.getElementById('s-disc').textContent      = fmt(s.discoveries);
  document.getElementById('s-el').textContent        = fmt(s.earth_likes);
  document.getElementById('s-bounties').textContent  = fmt(s.bounties);
  document.getElementById('s-credits').textContent   = fmtK(s.bounty_credits);
  document.getElementById('s-missions').textContent  = fmt(s.missions);
  document.getElementById('s-sessions').textContent  = fmt(s.sessions);
  document.getElementById('s-materials').textContent = fmtK(s.materials_collected || 0);
  document.getElementById('s-minerals').textContent  = fmtK(s.minerals_mined || 0);
}


// ── Shared scene-build helper used by both initial load + reload ──

function _applyJumpsToScene(jumps) {
  state.jumpsData = jumps.filter(j => j.x != null && j.y != null && j.z != null);

  slider.max   = Math.max(0, state.jumpsData.length - 1);
  slider.value = state.jumpsData.length - 1;
  state.currentIdx = state.jumpsData.length - 1;

  // Sync last-N slider max to total jump count
  const lastNSlider = document.getElementById('range-last-n');
  const lastNInput  = document.getElementById('input-last-n');
  if (lastNSlider) lastNSlider.max = state.jumpsData.length;
  if (lastNInput)  lastNInput.max  = state.jumpsData.length;

  tlProgress.textContent = `${state.jumpsData.length} / ${state.jumpsData.length}`;
  if (state.jumpsData.length) {
    const last = state.jumpsData[state.jumpsData.length - 1];
    tlDate.textContent = last.timestamp.replace('T', ' ').replace('Z', ' UTC');
  }

  // Build O(1) prefix-sum index BEFORE buildJumpScene / updateLiveStats call
  buildLiveStatsIndex();
  buildJumpScene(state.jumpsData);

  // Respect any active lastN filter on initial load too
  const drawEnd   = state.jumpsData.length;
  const drawStart = state.lastNJumps > 0 ? Math.max(0, drawEnd - state.lastNJumps) : 0;
  if (state.pointsGeo) state.pointsGeo.setDrawRange(drawStart, drawEnd - drawStart);
  if (state.pathGeo)   state.pathGeo.setDrawRange(drawStart,   drawEnd - drawStart);

  if (state.jumpsData.length) updateLiveStats(state.currentIdx);
  updateSystemInfo(state.currentIdx);
  if (state.jumpsData.length) resolveShipAt(state.jumpsData[state.currentIdx].timestamp);

  // Rebuild the bounty chart (if visible) against the new jump set.
  if (bountyChartVisible()) buildBountyChart();

  // With follow-cam on by default, snap the orbit target to the current jump
  // so the initial view is centered on the commander's latest position.
  if (state.followMode && state.jumpsData.length && state.currentIdx >= 0) {
    const j = state.jumpsData[state.currentIdx];
    orbit.target.set(j.x, j.y, j.z);
    followTarget.set(j.x, j.y, j.z);
    orbit.update();
  }
}


// ── Reload for commander filter change ──────────────────────────

export async function reloadScene() {
  document.getElementById('loading').style.display = 'flex';
  setLoading(10, 'Loading commander data…');
  stopPlay();

  const cmdParam = state.currentCommander
    ? `?commander=${encodeURIComponent(state.currentCommander)}` : '';

  try {
    setLoading(30, 'Fetching stats…');
    const [stats, jumps] = await Promise.all([
      fetch(`/api/stats${cmdParam}`).then(r => r.json()),
      fetch(`/api/jumps${cmdParam}`).then(r => r.json()),
      preloadLoadouts(),
    ]);
    resetShipResolverCache();   // force ship re-resolve after commander switch
    setLoading(70, 'Building scene…');
    updateStats(stats);
    _applyJumpsToScene(jumps);
    setLoading(100, 'Done');
    document.getElementById('loading').style.display = 'none';
  } catch (err) {
    document.getElementById('loading-status').textContent = 'Error: ' + err.message;
  }
}


// ── Initial load ────────────────────────────────────────────────

export async function loadData() {
  setLoading(10, 'Fetching galaxy data…');
  const [stats, jumps, commanders] = await Promise.all([
    fetch('/api/stats').then(r => r.json()),
    fetch('/api/jumps').then(r => r.json()),
    fetch('/api/commanders').then(r => r.json()).catch(() => []),
    preloadLoadouts(),
  ]);

  setLoading(60, 'Building scene…');
  updateStats(stats);
  _applyJumpsToScene(jumps);

  // ── Commander dropdown ──
  const cmdRow = document.getElementById('commander-row');
  const cmdSel = document.getElementById('sel-commander');

  if (commanders.length > 1) {
    commanders.forEach(c => {
      const opt = document.createElement('option');
      opt.value       = c.fid || '';
      opt.textContent = `${c.name || c.fid} (${(c.jump_count || 0).toLocaleString()})`;
      cmdSel.appendChild(opt);
    });
    cmdRow.style.display = '';
    cmdSel.addEventListener('change', e => {
      state.currentCommander = e.target.value || null;
      reloadScene();
    });
  } else if (commanders.length === 1 && commanders[0].name) {
    const logo = document.querySelector('#stats-bar .logo');
    if (logo) logo.textContent = commanders[0].name;
  }

  setLoading(100, 'Done');
  document.getElementById('loading').style.display = 'none';
}


// ── followTarget is used by main.js animate() — re-export for it ──

export { followTarget };
