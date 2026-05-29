// ═══════════════════════════════════════════════════════════════
// panels.js — all DOM-heavy panels and the click/hover layer:
//   • detail panel (right)   — per-system drill-down
//   • bounty panel (left)    — aggregated combat stats with timeline filter
//   • mining panel (right)   — aggregated mining stats with timeline filter
//   • system info (bottom-r) — current jump's headline numbers
//   • tooltip + hover raycaster
// ═══════════════════════════════════════════════════════════════

import { state } from './state.js';
import { fmtCr } from './constants.js';
import { camera, renderer, clickLock } from './scene.js';

// ── DOM refs ────────────────────────────────────────────────────

const tooltip      = document.getElementById('tooltip');
const detailPanel  = document.getElementById('detail-panel');
const detailBody   = document.getElementById('detail-body');
const detailTitle  = document.getElementById('detail-title');
const btnClose     = document.getElementById('btn-close');

const bountyPanel    = document.getElementById('bounty-panel');
const bountyBody     = document.getElementById('bounty-body');
const btnBountyLog   = document.getElementById('btn-bounty-log');
const btnCloseBounty = document.getElementById('btn-close-bounty');

const miningPanel    = document.getElementById('mining-panel');
const miningBody     = document.getElementById('mining-body');
const btnMiningLog   = document.getElementById('btn-mining-log');
const btnCloseMining = document.getElementById('btn-close-mining');

// ── Raycaster (shared by click + hover) ─────────────────────────

const raycaster = new THREE.Raycaster();
raycaster.params.Points.threshold = 25;

const mouse = new THREE.Vector2();
function updateMouse(e) {
  mouse.x =  (e.clientX / innerWidth)  * 2 - 1;
  mouse.y = -(e.clientY / innerHeight) * 2 + 1;
}


// ═══════════════════════════════════════════════════════════════
// DETAIL PANEL
// ═══════════════════════════════════════════════════════════════

function renderDetailPanel(data, jumpRow) {
  const { jump, scans, bounties } = data;

  const fmt  = n => n == null ? '—' : Number(n).toLocaleString();
  const fmtF = n => n == null ? '—' : Number(n).toFixed(2);

  let html = '';

  // ── Jump info ──
  html += `<div class="detail-section">
    <div class="detail-section-title">Jump Info</div>
    <div class="detail-row"><span class="key">System</span><span class="val">${jump.star_system || '—'}</span></div>
    <div class="detail-row"><span class="key">Arrived</span><span class="val">${jump.jump_time || '—'}</span></div>
    <div class="detail-row"><span class="key">Jump dist</span><span class="val">${fmtF(jump.jump_dist)} LY</span></div>
    <div class="detail-row"><span class="key">Dist from Sol</span><span class="val">${fmt(jump.dist_from_sol_ly)} LY</span></div>
    <div class="detail-row"><span class="key">Coords</span><span class="val">${fmtF(jump.x)}, ${fmtF(jump.y)}, ${fmtF(jump.z)}</span></div>`;
  if (jump.security)   html += `<div class="detail-row"><span class="key">Security</span><span class="val">${jump.security}</span></div>`;
  if (jump.population) html += `<div class="detail-row"><span class="key">Population</span><span class="val">${fmt(jump.population)}</span></div>`;
  html += `</div>`;

  // Partition scans into three groups
  const isEL       = s => (s.body_type || '').toLowerCase().includes('earthlike');
  const firstDiscs = scans.filter(s => s.was_discovered && !isEL(s));
  const earthLikes = scans.filter(s => isEL(s));
  const otherBodies= scans.filter(s => !s.was_discovered && !isEL(s));

  if (firstDiscs.length || earthLikes.length) {
    html += `<div class="detail-row" style="gap:8px;margin-bottom:10px">`;
    if (firstDiscs.length) html += `<span style="color:var(--ed-green);font-size:0.65rem">★ ${firstDiscs.length} First Discovery</span>`;
    if (earthLikes.length) html += `<span style="color:var(--ed-cyan);font-size:0.65rem">🌍 ${earthLikes.length} Earth-Like</span>`;
    html += `</div>`;
  }

  // ── First Discoveries ──
  if (firstDiscs.length) {
    html += `<div class="detail-section">
      <div class="detail-section-title">★ First Discoveries (${firstDiscs.length})</div>`;
    firstDiscs.forEach(s => {
      const meta = [
        s.dist_ls != null ? `${s.dist_ls} Ls` : null,
        s.landable ? 'Landable' : null,
        s.atmosphere && s.atmosphere !== 'None' ? s.atmosphere : null,
      ].filter(Boolean).join(' · ');
      html += `<div class="scan-item">
        <div class="scan-name" style="color:var(--ed-green)">${s.body_name || '—'}</div>
        <div class="scan-meta">${s.body_type || '—'}${meta ? ' · ' + meta : ''}</div>
        ${s.was_mapped ? '<span class="scan-disc">✦ MAPPED</span>' : ''}
      </div>`;
    });
    html += `</div>`;
  }

  // ── Earth-Like Worlds ──
  if (earthLikes.length) {
    html += `<div class="detail-section">
      <div class="detail-section-title">🌍 Earth-Like Worlds (${earthLikes.length})</div>`;
    earthLikes.forEach(s => {
      html += `<div class="scan-item">
        <div class="scan-name" style="color:var(--ed-cyan)">${s.body_name || '—'}</div>
        <div class="scan-meta">${s.dist_ls != null ? s.dist_ls + ' Ls' : ''}
          ${s.was_discovered ? ' · <span style="color:var(--ed-green)">★ First Discovery</span>' : ''}
          ${s.was_mapped    ? ' · ✦ Mapped' : ''}
        </div>
      </div>`;
    });
    html += `</div>`;
  }

  // ── Bounties ──
  if (bounties.length) {
    html += `<div class="detail-section"><div class="detail-section-title">⚔ Bounties (${bounties.length})</div>`;
    bounties.forEach(b => {
      html += `<div class="bounty-item">
        <div class="scan-name" style="color:var(--ed-red)">${b.ship || '—'}</div>
        <div class="scan-meta">${b.victim_faction || ''} · ${Number(b.total_reward).toLocaleString()} Cr · ${b.time || ''}</div>
      </div>`;
    });
    html += `</div>`;
  }

  if (otherBodies.length) {
    html += `<div style="color:#4a7a9b;font-size:0.62rem;margin-bottom:8px">${otherBodies.length} other bod${otherBodies.length === 1 ? 'y' : 'ies'} scanned (not first discoveries)</div>`;
  }

  if (!scans.length && !bounties.length) {
    html += `<div style="color:#4a7a9b;font-size:0.65rem">No discoveries or combat recorded for this visit.</div>`;
  }

  detailBody.innerHTML = html;
}

renderer.domElement.addEventListener('click', async e => {
  if (!state.pointsMesh || !state.jumpsData.length) return;
  updateMouse(e);
  raycaster.setFromCamera(mouse, camera);

  // Only raycast visible points (up to currentIdx)
  const visGeo = new THREE.BufferGeometry();
  const allPos = state.pointsGeo.attributes.position.array;
  const visCnt = Math.min(state.currentIdx + 1, state.jumpsData.length) * 3;
  visGeo.setAttribute('position', new THREE.BufferAttribute(allPos.slice(0, visCnt), 3));
  const tempPoints = new THREE.Points(visGeo, state.pointsMesh.material);
  const hits = raycaster.intersectObject(tempPoints);
  visGeo.dispose();

  if (!hits.length) return;
  const idx = hits[0].index;
  const j   = state.jumpsData[idx];
  if (!j) return;

  detailTitle.textContent = j.star_system;
  detailBody.innerHTML    = `<div style="color:#4a7a9b;font-size:0.62rem;margin-bottom:8px">Loading…</div>`;
  detailPanel.classList.add('open');

  try {
    // Scope the drill-down to THIS visit (the clicked jump's timestamp).
    const visitQS = j.timestamp ? `?visit=${encodeURIComponent(j.timestamp)}` : '';
    const res     = await fetch(`/api/system/${j.system_address}${visitQS}`);
    const data    = await res.json();
    renderDetailPanel(data, j);
  } catch (err) {
    detailBody.innerHTML = `<div style="color:#ff1744">Error loading system data.</div>`;
  }
});

btnClose.addEventListener('click', () => detailPanel.classList.remove('open'));


// ═══════════════════════════════════════════════════════════════
// HOVER TOOLTIP
// ═══════════════════════════════════════════════════════════════

let lastMouseX = 0, lastMouseY = 0;
let frameCount = 0;

renderer.domElement.addEventListener('mousemove', e => {
  lastMouseX = e.clientX; lastMouseY = e.clientY;
  updateMouse(e);
});

function checkHover() {
  if (!state.pointsMesh || !state.jumpsData.length) return;
  raycaster.setFromCamera(mouse, camera);
  const hits = raycaster.intersectObject(state.pointsMesh);
  const el   = tooltip;

  if (hits.length) {
    const idx = hits[0].index;
    // Don't hover on future jumps (beyond timeline cursor)
    if (idx >= state.currentIdx + 1) { el.style.display = 'none'; return; }
    // ... or on jumps clipped out by the lastN filter
    if (state.lastNJumps > 0) {
      const drawStart = Math.max(0, state.currentIdx + 1 - state.lastNJumps);
      if (idx < drawStart) { el.style.display = 'none'; return; }
    }
    const j  = state.jumpsData[idx];
    let tip  = `<strong style="color:var(--ed-blue)">${j.star_system}</strong><br>`;
    tip += `${j.timestamp ? j.timestamp.replace('T',' ').replace('Z',' UTC') : ''}`;
    if (j.first_discoveries)  tip += `<br><span style="color:var(--ed-green)">★ ${j.first_discoveries} discovery</span>`;
    if (j.earth_likes)        tip += `<br><span style="color:var(--ed-cyan)">🌍 ${j.earth_likes} earth-like</span>`;
    if (j.bounties_collected) tip += `<br><span style="color:var(--ed-red)">⚔ ${j.bounties_collected} bounties</span>`;
    el.innerHTML = tip;
    el.style.display = 'block';
    el.style.left = (lastMouseX + 16) + 'px';
    el.style.top  = (lastMouseY + 16) + 'px';
  } else {
    el.style.display = 'none';
  }
}

// Called from main.js animate loop. We throttle inside there too.
export function maybeCheckHover(every = 4) {
  frameCount++;
  if (state.followMode) return;       // skip while follow-cam is on (saves CPU)
  if (frameCount % every !== 0) return;
  checkHover();
}


// ═══════════════════════════════════════════════════════════════
// SYSTEM INFO PANEL (bottom-right)
// ═══════════════════════════════════════════════════════════════

export function updateSystemInfo(idx) {
  const body = document.getElementById('sys-info-body');
  if (!state.jumpsData.length || idx < 0) {
    body.innerHTML = `<div style="color:#4a7a9b;font-size:0.62rem">No system</div>`;
    return;
  }
  const j = state.jumpsData[idx];
  if (!j) return;

  const dist = Math.sqrt((j.x||0)*(j.x||0) + (j.y||0)*(j.y||0) + (j.z||0)*(j.z||0));

  const secLow = (j.security || '').toLowerCase();
  const secCls = secLow.includes('high') ? 'green'
              : secLow.includes('med')   ? ''
              : secLow.includes('low') || secLow.includes('anarchy') ? 'red'
              : '';

  const row = (lbl, val, cls = '') =>
    `<div class="si-row"><span class="si-key">${lbl}</span>` +
    `<span class="si-val${cls ? ' ' + cls : ''}">${val}</span></div>`;

  let html = '';
  html += row('System', `<strong style="color:var(--ed-blue);letter-spacing:1px">${j.star_system || '—'}</strong>`);
  html += row('Dist from Sol', `${dist.toFixed(1)} LY`);
  html += row('Jump dist',     `${j.jump_dist != null ? Number(j.jump_dist).toFixed(2) : '—'} LY`);
  if (j.security)   html += row('Security',   j.security, secCls);
  if (j.population) html += row('Population', Number(j.population).toLocaleString());
  if (j.first_discoveries > 0) html += row('Discoveries', `★ ${j.first_discoveries}`, 'green');
  if (j.earth_likes        > 0) html += row('Earth-Likes', `🌍 ${j.earth_likes}`,   'cyan');

  html += `<div class="si-coords">${
    (j.x||0).toFixed(1)}, ${(j.y||0).toFixed(1)}, ${(j.z||0).toFixed(1)
  }</div>`;
  body.innerHTML = html;
}


// ═══════════════════════════════════════════════════════════════
// BOUNTY PANEL
// ═══════════════════════════════════════════════════════════════

let _bountyRefreshTimer = null;
let _bountyPlayInterval = null;
let _lastBountyHTML     = null;

function renderBountyPanel(data) {
  const { totals, by_ship, by_faction, by_year, top_kills } = data;
  const fmt = n => Number(n).toLocaleString();

  let html = '';

  // ── Totals ──
  html += `<div class="bounty-totals-grid">
    <div class="bounty-total-card">
      <div class="btc-label">SHIPS DESTROYED</div>
      <div class="btc-value">${fmt(totals.total_kills)}</div>
    </div>
    <div class="bounty-total-card">
      <div class="btc-label">TOTAL CREDITS</div>
      <div class="btc-value amber">${fmtCr(totals.total_credits)} Cr</div>
    </div>
    <div class="bounty-total-card">
      <div class="btc-label">AVG PER KILL</div>
      <div class="btc-value amber">${fmtCr(totals.avg_reward)} Cr</div>
    </div>
    <div class="bounty-total-card">
      <div class="btc-label">SHIP TYPES / FACTIONS</div>
      <div class="btc-value">${fmt(totals.unique_ships)} / ${fmt(totals.unique_factions)}</div>
    </div>
  </div>`;

  if (by_ship.length) {
    const maxKills = by_ship[0].kills;
    html += `<div class="b-section">
      <div class="b-section-title">Ships Destroyed (${by_ship.length} types)</div>`;
    by_ship.forEach((s, i) => {
      const pct = maxKills > 0 ? (s.kills / maxKills * 100).toFixed(1) : 0;
      html += `<div class="b-row">
        <span class="b-rank">${i + 1}</span>
        <span class="b-name" title="${s.ship}">${s.ship}</span>
        <span class="b-kills">${fmt(s.kills)}</span>
        <div class="b-bar-wrap"><div class="b-bar" style="width:${pct}%"></div></div>
        <span class="b-credits">${fmtCr(s.total_credits)}</span>
      </div>`;
    });
    html += `</div>`;
  }

  if (by_faction.length) {
    const maxKills = by_faction[0].kills;
    html += `<div class="b-section">
      <div class="b-section-title">Factions Hunted (${by_faction.length})</div>`;
    by_faction.forEach((f, i) => {
      const pct = maxKills > 0 ? (f.kills / maxKills * 100).toFixed(1) : 0;
      html += `<div class="b-row">
        <span class="b-rank">${i + 1}</span>
        <span class="b-name" title="${f.faction}">${f.faction}</span>
        <span class="b-kills">${fmt(f.kills)}</span>
        <div class="b-bar-wrap"><div class="b-bar" style="width:${pct}%"></div></div>
        <span class="b-credits">${fmtCr(f.total_credits)}</span>
      </div>`;
    });
    html += `</div>`;
  }

  if (by_year.length) {
    const maxKills = Math.max(...by_year.map(y => y.kills));
    html += `<div class="b-section">
      <div class="b-section-title">Activity by Year</div>
      <div class="year-grid">`;
    by_year.forEach(y => {
      const pct = maxKills > 0 ? (y.kills / maxKills * 100).toFixed(1) : 0;
      html += `<div class="year-row">
        <span class="year-lbl">${y.year}</span>
        <div class="year-bar-wrap"><div class="year-bar" style="width:${pct}%"></div></div>
        <span class="year-val">${fmt(y.kills)} kills</span>
        <span class="year-cr">${fmtCr(y.total_credits)}</span>
      </div>`;
    });
    html += `</div></div>`;
  }

  if (top_kills.length) {
    html += `<div class="b-section">
      <div class="b-section-title">Most Valuable Kills</div>`;
    top_kills.forEach(k => {
      html += `<div class="tk-row">
        <span class="tk-ship">${k.ship}</span>
        <span class="tk-meta">${k.faction} · ${k.time}</span>
        <span class="tk-reward">${fmtCr(k.total_reward)} Cr</span>
      </div>`;
    });
    html += `</div>`;
  }

  // Diff-skip: avoid reflow + animation restart when nothing changed.
  if (html === _lastBountyHTML) return;
  _lastBountyHTML = html;
  bountyBody.innerHTML = html;
}

async function refreshBountyIfOpen() {
  if (!bountyPanel.classList.contains('open') || !state.jumpsData.length) return;
  const j = state.jumpsData[state.currentIdx];
  if (!j) return;
  try {
    const url  = `/api/bounties/summary?before=${encodeURIComponent(j.timestamp)}`;
    const data = await fetch(url).then(r => r.json());
    renderBountyPanel(data);
  } catch (_) {}
}

export function startBountyPlayRefresh() {
  clearInterval(_bountyPlayInterval);
  _bountyPlayInterval = setInterval(refreshBountyIfOpen, 1000);
}

export function stopBountyPlayRefresh() {
  clearInterval(_bountyPlayInterval);
  _bountyPlayInterval = null;
  refreshBountyIfOpen();
}

export function scheduleBountyRefresh() {
  if (state.isPlaying) return;
  if (!bountyPanel || !bountyPanel.classList.contains('open')) return;
  clearTimeout(_bountyRefreshTimer);
  _bountyRefreshTimer = setTimeout(refreshBountyIfOpen, 400);
}

async function openBountyPanel() {
  bountyPanel.classList.add('open');
  bountyBody.innerHTML = `<div style="color:#4a7a9b;font-size:0.65rem">Loading…</div>`;
  _lastBountyHTML = null;

  const j   = state.jumpsData.length ? state.jumpsData[state.currentIdx] : null;
  const url = j
    ? `/api/bounties/summary?before=${encodeURIComponent(j.timestamp)}`
    : '/api/bounties/summary';

  try {
    const data = await fetch(url).then(r => r.json());
    renderBountyPanel(data);
  } catch (err) {
    bountyBody.innerHTML = `<div style="color:var(--ed-red)">Error: ${err.message}</div>`;
  }
}

btnBountyLog.addEventListener('click', () =>
  bountyPanel.classList.contains('open')
    ? bountyPanel.classList.remove('open')
    : openBountyPanel(),
);
btnCloseBounty.addEventListener('click', () => bountyPanel.classList.remove('open'));


// ═══════════════════════════════════════════════════════════════
// MINING PANEL
// ═══════════════════════════════════════════════════════════════

let _miningRefreshTimer = null;
let _miningPlayInterval = null;
let _lastMiningHTML     = null;

function renderMiningPanel(data) {
  const { totals, by_material, by_year, recent } = data;
  const fmt = n => Number(n).toLocaleString();

  let html = '';

  html += `<div class="mining-totals-grid">
    <div class="mining-total-card">
      <div class="mtc-label">UNITS REFINED</div>
      <div class="mtc-value">${fmt(totals.total_refined)}</div>
    </div>
    <div class="mining-total-card">
      <div class="mtc-label">MATERIALS FOUND</div>
      <div class="mtc-value">${fmt(totals.unique_materials)}</div>
    </div>
  </div>`;

  if (by_material.length) {
    const maxCount = by_material[0].count;
    html += `<div class="m-section">
      <div class="m-section-title">Materials Refined (${by_material.length} types)</div>`;
    by_material.forEach((m, i) => {
      const pct = maxCount > 0 ? (m.count / maxCount * 100).toFixed(1) : 0;
      html += `<div class="m-row">
        <span class="m-rank">${i + 1}</span>
        <span class="m-name" title="${m.material}">${m.material}</span>
        <span class="m-count">${fmt(m.count)}</span>
        <div class="m-bar-wrap"><div class="m-bar" style="width:${pct}%"></div></div>
      </div>`;
    });
    html += `</div>`;
  }

  if (by_year.length) {
    const maxCount = Math.max(...by_year.map(y => y.count));
    html += `<div class="m-section">
      <div class="m-section-title">Activity by Year</div>
      <div class="m-year-grid">`;
    by_year.forEach(y => {
      const pct = maxCount > 0 ? (y.count / maxCount * 100).toFixed(1) : 0;
      html += `<div class="m-year-row">
        <span class="m-year-lbl">${y.year}</span>
        <div class="m-year-bar-wrap"><div class="m-year-bar" style="width:${pct}%"></div></div>
        <span class="m-year-val">${fmt(y.count)} units</span>
      </div>`;
    });
    html += `</div></div>`;
  }

  if (recent.length) {
    html += `<div class="m-section">
      <div class="m-section-title">Recent Refining</div>`;
    recent.forEach(r => {
      html += `<div class="m-recent-row">
        <span class="m-recent-mat">${r.material}</span>
        <span class="m-recent-time">${r.time}</span>
      </div>`;
    });
    html += `</div>`;
  }

  if (!by_material.length) {
    html += `<div style="color:#4a7a9b;font-size:0.65rem">No mining data recorded yet.</div>`;
  }

  if (html === _lastMiningHTML) return;
  _lastMiningHTML = html;
  miningBody.innerHTML = html;
}

async function refreshMiningIfOpen() {
  if (!miningPanel.classList.contains('open') || !state.jumpsData.length) return;
  const j = state.jumpsData[state.currentIdx];
  if (!j) return;
  try {
    const url  = `/api/mining/summary?before=${encodeURIComponent(j.timestamp)}`;
    const data = await fetch(url).then(r => r.json());
    renderMiningPanel(data);
  } catch (_) {}
}

export function startMiningPlayRefresh() {
  clearInterval(_miningPlayInterval);
  _miningPlayInterval = setInterval(refreshMiningIfOpen, 1000);
}

export function stopMiningPlayRefresh() {
  clearInterval(_miningPlayInterval);
  _miningPlayInterval = null;
  refreshMiningIfOpen();
}

export function scheduleMiningRefresh() {
  if (state.isPlaying) return;
  if (!miningPanel || !miningPanel.classList.contains('open')) return;
  clearTimeout(_miningRefreshTimer);
  _miningRefreshTimer = setTimeout(refreshMiningIfOpen, 400);
}

async function openMiningPanel() {
  miningPanel.classList.add('open');
  miningBody.innerHTML = `<div style="color:#4a7a9b;font-size:0.65rem">Loading…</div>`;
  _lastMiningHTML = null;

  const j   = state.jumpsData.length ? state.jumpsData[state.currentIdx] : null;
  const url = j
    ? `/api/mining/summary?before=${encodeURIComponent(j.timestamp)}`
    : '/api/mining/summary';

  try {
    const data = await fetch(url).then(r => r.json());
    renderMiningPanel(data);
  } catch (err) {
    miningBody.innerHTML = `<div style="color:var(--ed-green)">Error: ${err.message}</div>`;
  }
}

btnMiningLog.addEventListener('click', () =>
  miningPanel.classList.contains('open')
    ? miningPanel.classList.remove('open')
    : openMiningPanel(),
);
btnCloseMining.addEventListener('click', () => miningPanel.classList.remove('open'));
