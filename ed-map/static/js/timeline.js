// ═══════════════════════════════════════════════════════════════
// timeline.js — slider, play/pause, last-N filter, bounty-activity
//               chart aligned to the slider, and the central
//               setIndex() that drives every cursor-aware update.
// ═══════════════════════════════════════════════════════════════

import { SPEED_CFG } from './constants.js';
import { state } from './state.js';
import { updateActiveMarker, updateLiveStats } from './jumps.js';
import {
  updateSystemInfo,
  scheduleBountyRefresh, scheduleMiningRefresh,
  startBountyPlayRefresh, stopBountyPlayRefresh,
  startMiningPlayRefresh, stopMiningPlayRefresh,
} from './panels.js';
import { resolveShipAt, snapShipToCurrent } from './ship-viewer.js';
import { orbit } from './scene.js';

// ── DOM refs ────────────────────────────────────────────────────

const slider     = document.getElementById('slider');
const btnPlay    = document.getElementById('btn-play');
const btnReset   = document.getElementById('btn-reset');
const tlDate     = document.getElementById('timeline-date');
const tlProgress = document.getElementById('timeline-progress');


// ═══════════════════════════════════════════════════════════════
// setIndex — the only function allowed to mutate state.currentIdx
// ═══════════════════════════════════════════════════════════════

export function setIndex(idx) {
  if (!state.jumpsData.length) return;
  state.currentIdx = Math.max(0, Math.min(state.jumpsData.length - 1, idx));
  slider.value = state.currentIdx;

  const drawEnd   = state.currentIdx + 1;
  const drawStart = state.lastNJumps > 0 ? Math.max(0, drawEnd - state.lastNJumps) : 0;
  const drawCount = drawEnd - drawStart;
  if (state.pointsGeo) state.pointsGeo.setDrawRange(drawStart, drawCount);
  if (state.pathGeo)   state.pathGeo.setDrawRange(drawStart,   drawCount);

  const j = state.jumpsData[state.currentIdx];
  tlDate.textContent     = j ? j.timestamp.replace('T', ' ').replace('Z', ' UTC') : '—';
  tlProgress.textContent = `${state.currentIdx + 1} / ${state.jumpsData.length}`;

  updateLiveStats(state.currentIdx);
  updateSystemInfo(state.currentIdx);
  updateActiveMarker();
  updateBountyChartMarker();

  if (j) resolveShipAt(j.timestamp);
  scheduleBountyRefresh();
  scheduleMiningRefresh();
}


// ═══════════════════════════════════════════════════════════════
// Step / play / stop
// ═══════════════════════════════════════════════════════════════

export function stepForward() {
  if (state.currentIdx >= state.jumpsData.length - 1) { stopPlay(); return; }
  setIndex(state.currentIdx + 1);
}

export function stepBackward() {
  if (state.currentIdx <= 0) return;
  setIndex(state.currentIdx - 1);
}

export function startPlay() {
  if (state.currentIdx >= state.jumpsData.length - 1) setIndex(0);
  state.isPlaying = true;
  btnPlay.textContent = '⏸ PAUSE';
  btnPlay.classList.add('playing');
  const speedKey   = document.getElementById('sel-speed').value;
  const [ms, steps] = SPEED_CFG[speedKey] || [1000, 1];
  state.playInterval = setInterval(() => {
    for (let s = 0; s < steps; s++) stepForward();
  }, ms);
  startBountyPlayRefresh();
  startMiningPlayRefresh();
}

export function stopPlay() {
  state.isPlaying = false;
  btnPlay.textContent = '▶ PLAY';
  btnPlay.classList.remove('playing');
  if (state.playInterval) { clearInterval(state.playInterval); state.playInterval = null; }
  stopBountyPlayRefresh();
  stopMiningPlayRefresh();
  // Make sure the ship matches the stopped-on position
  snapShipToCurrent();
}


// ═══════════════════════════════════════════════════════════════
// Bounty activity chart — aligned to slider track
// ═══════════════════════════════════════════════════════════════
// A toggle-able wave/bar strip above the timeline showing per-bucket
// bounty_credits across all jumps. Buckets are computed from jumpsData
// and aggregated linearly over index space (not time), so the chart's
// X-axis aligns 1:1 with the timeline slider position.

let _bcVisible = false;

function _alignBountyChart() {
  const wrap = document.getElementById('bounty-chart');
  if (!wrap || !slider) return;
  const r = slider.getBoundingClientRect();
  wrap.style.left  = r.left  + 'px';
  wrap.style.width = r.width + 'px';
  wrap.style.right = 'auto';
}

export function buildBountyChart() {
  const wrap   = document.getElementById('bounty-chart');
  const canvas = document.getElementById('bounty-chart-canvas');
  const peakEl = document.getElementById('bounty-chart-peak');
  if (!wrap || !canvas || !_bcVisible) return;

  _alignBountyChart();

  const rect = wrap.getBoundingClientRect();
  const dpr  = Math.min(devicePixelRatio, 2);
  const W    = Math.max(1, Math.floor(rect.width  * dpr));
  const H    = Math.max(1, Math.floor(rect.height * dpr));
  canvas.width  = W;
  canvas.height = H;
  canvas.style.width  = rect.width  + 'px';
  canvas.style.height = rect.height + 'px';

  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, W, H);

  if (!state.jumpsData.length) {
    peakEl.textContent = '—';
    updateBountyChartMarker();
    return;
  }

  // One bucket per ~3 CSS pixels, clamped to jump count.
  const pxPerBar = 3 * dpr;
  const nBuckets = Math.max(1, Math.min(state.jumpsData.length, Math.floor(W / pxPerBar)));
  const n        = state.jumpsData.length;
  const buckets  = new Float64Array(nBuckets);

  for (let i = 0; i < n; i++) {
    const b = Number(state.jumpsData[i].bounty_credits) || 0;
    if (b <= 0) continue;
    const bi = Math.min(nBuckets - 1, Math.floor(i / n * nBuckets));
    buckets[bi] += b;
  }

  let max = 0;
  for (let i = 0; i < nBuckets; i++) if (buckets[i] > max) max = buckets[i];

  // Bottom baseline
  ctx.fillStyle = 'rgba(255, 23, 68, 0.15)';
  ctx.fillRect(0, H - 1, W, 1);

  if (max > 0) {
    const barW    = W / nBuckets;
    const logBase = Math.log10(1 + max);
    const usableH = H - 4;
    for (let i = 0; i < nBuckets; i++) {
      const v = buckets[i];
      if (v <= 0) continue;
      // Log scale so one massive pirate run doesn't flatten everything else.
      const t     = Math.log10(1 + v) / logBase;
      const barH  = Math.max(1, Math.round(t * usableH));
      const alpha = 0.35 + 0.60 * t;
      ctx.fillStyle = `rgba(255, 23, 68, ${alpha.toFixed(3)})`;
      ctx.fillRect(Math.floor(i * barW), H - barH - 1, Math.max(1, Math.floor(barW) - 0.5), barH);
    }

    peakEl.textContent = 'Peak ' + (function (v) {
      if (v >= 1e9) return (v / 1e9).toFixed(1) + 'B CR';
      if (v >= 1e6) return (v / 1e6).toFixed(1) + 'M CR';
      if (v >= 1e3) return (v / 1e3).toFixed(1) + 'K CR';
      return Math.round(v).toLocaleString() + ' CR';
    })(max);
  } else {
    peakEl.textContent = 'No bounties';
  }

  updateBountyChartMarker();
}

export function updateBountyChartMarker() {
  const marker = document.getElementById('bounty-chart-marker');
  const wrap   = document.getElementById('bounty-chart');
  if (!marker || !wrap || !_bcVisible) return;
  const rect = wrap.getBoundingClientRect();
  const n    = state.jumpsData.length;
  const x    = n > 1 ? (state.currentIdx / (n - 1)) * rect.width : 0;
  marker.style.left = x + 'px';
}

// True if the chart strip is currently visible (used by data.js to
// rebuild it after a fresh jump load).
export function bountyChartVisible() {
  return _bcVisible;
}

document.getElementById('btn-bounty-chart').addEventListener('click', () => {
  _bcVisible = !_bcVisible;
  const wrap = document.getElementById('bounty-chart');
  const btn  = document.getElementById('btn-bounty-chart');
  wrap.style.display = _bcVisible ? 'block' : 'none';
  btn.classList.toggle('active', _bcVisible);
  if (_bcVisible) buildBountyChart();
});

// Debounced resize: rebuild bars + realign to slider
let _bcResizeTimer = null;
window.addEventListener('resize', () => {
  clearTimeout(_bcResizeTimer);
  _bcResizeTimer = setTimeout(() => {
    if (_bcVisible) buildBountyChart();
  }, 150);
});


// ═══════════════════════════════════════════════════════════════
// Last-N jumps filter (slider + numeric input, bidirectional)
// ═══════════════════════════════════════════════════════════════

function applyLastN(rawValue, source) {
  const maxN = state.jumpsData.length || 0;
  let v = parseInt(rawValue, 10);
  if (isNaN(v) || v < 0) v = 0;
  if (maxN > 0 && v > maxN) v = maxN;
  state.lastNJumps = v;

  const lastNSlider = document.getElementById('range-last-n');
  const lastNInput  = document.getElementById('input-last-n');
  if (source !== 'slider' && lastNSlider) lastNSlider.value = v;
  if (source !== 'input'  && lastNInput)  lastNInput.value  = v;

  document.getElementById('last-n-label').textContent = v === 0 ? 'All' : v.toLocaleString();
  setIndex(state.currentIdx);
}

document.getElementById('range-last-n').addEventListener('input', e => {
  applyLastN(e.target.value, 'slider');
});
document.getElementById('input-last-n').addEventListener('change', e => {
  applyLastN(e.target.value, 'input');
});
document.getElementById('input-last-n').addEventListener('keydown', e => {
  if (e.key === 'Enter') { e.preventDefault(); applyLastN(e.target.value, 'input'); e.target.blur(); }
});


// ═══════════════════════════════════════════════════════════════
// Wire timeline + view-control listeners
// ═══════════════════════════════════════════════════════════════

btnPlay.addEventListener('click',  () => state.isPlaying ? stopPlay() : startPlay());
btnReset.addEventListener('click', () => { stopPlay(); setIndex(0); });
slider.addEventListener('input',   () => { stopPlay(); setIndex(parseInt(slider.value, 10)); });

document.getElementById('btn-step-back').addEventListener('click', () => { stopPlay(); stepBackward(); });
document.getElementById('btn-step-fwd' ).addEventListener('click', () => { stopPlay(); stepForward();  });

document.getElementById('sel-speed').addEventListener('change', () => {
  if (state.isPlaying) { stopPlay(); startPlay(); }
});

document.getElementById('sel-follow').addEventListener('change', e => {
  state.followMode = e.target.value === '1';
  if (state.followMode && state.jumpsData.length && state.currentIdx >= 0) {
    const j = state.jumpsData[state.currentIdx];
    orbit.target.set(j.x, j.y, j.z);
    orbit.update();
  }
});

document.getElementById('sel-path').addEventListener('change', e => {
  if (state.pathLine) state.pathLine.visible = e.target.value === '1';
});

document.getElementById('range-size').addEventListener('input', e => {
  if (state.pointsMesh) state.pointsMesh.material.size = parseFloat(e.target.value);
});


// ── Re-export DOM refs that data.js needs ──

export { slider, tlDate, tlProgress };
