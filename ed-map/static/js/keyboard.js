// ═══════════════════════════════════════════════════════════════
// keyboard.js — global keyboard shortcuts
// ───────────────────────────────────────────────────────────────
//   W/A/S/D   pan orbit target (screen-relative, on galactic plane)
//   Q / E     pan up / down (world Y)
//   F         toggle follow-cam
//   B / M / X toggle bounty log / mining log / bounty activity chart
//   Space     play / pause
//   0         restart timeline (jump to 0, stop play)
//   1..6      speed: 0.25× / 0.5× / 1× / 5× / 20× / 100×
//
// Single-shot keys reuse the existing button click / select-change
// handlers via synthetic events, so there's only one source of truth
// for what each toggle does. Movement keys are continuous — held keys
// are tracked in a Set and applied per frame from main.js's animate()
// via tickCamera().
// ═══════════════════════════════════════════════════════════════

import { state } from './state.js';
import { camera, orbit } from './scene.js';

// Order matches keys 1..6 → SPEED_CFG entries in constants.js
const SPEED_KEYS = ['0.25', '0.5', '1', '5', '20', '100'];

const heldKeys = new Set();

function isTextInputFocused() {
  const el = document.activeElement;
  if (!el || el === document.body) return false;
  const tag = el.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA') return true;
  if (tag === 'SELECT') return true;   // also skip while a dropdown is focused
  return el.isContentEditable === true;
}

function fireChange(el) {
  el.dispatchEvent(new Event('change', { bubbles: true }));
}


// ── Keyboard cheatsheet overlay ─────────────────────────────────

function toggleKeysPanel(force) {
  const panel = document.getElementById('keys-panel');
  const btn   = document.getElementById('btn-keys');
  if (!panel || !btn) return;
  const open = force === undefined ? !panel.classList.contains('open') : force;
  panel.classList.toggle('open', open);
  panel.setAttribute('aria-hidden', open ? 'false' : 'true');
  btn.classList.toggle('active', open);
}

document.getElementById('btn-keys')?.addEventListener('click', () => toggleKeysPanel());
document.getElementById('btn-close-keys')?.addEventListener('click', () => toggleKeysPanel(false));


// ── keydown ─────────────────────────────────────────────────────

window.addEventListener('keydown', e => {
  if (isTextInputFocused()) return;
  // Don't hijack browser shortcuts
  if (e.ctrlKey || e.metaKey || e.altKey) return;

  const k = e.key.length === 1 ? e.key.toLowerCase() : e.key;

  // ── Movement (continuous — track held state) ──
  if ('wasdqe'.includes(k)) {
    if (!heldKeys.has(k)) {
      heldKeys.add(k);
      // First press in a movement gesture turns follow-cam off, otherwise
      // it would yank the target right back to the current jump every frame.
      if (state.followMode) {
        state.followMode = false;
        const sel = document.getElementById('sel-follow');
        if (sel) sel.value = '0';
      }
    }
    e.preventDefault();
    return;
  }

  // ── Single-shot keys ──
  switch (k) {
    case 'b':
      document.getElementById('btn-bounty-log').click();
      e.preventDefault();
      break;

    case 'm':
      document.getElementById('btn-mining-log').click();
      e.preventDefault();
      break;

    case 'x':
      document.getElementById('btn-bounty-chart').click();
      e.preventDefault();
      break;

    case 'f': {
      const sel = document.getElementById('sel-follow');
      if (sel) {
        sel.value = sel.value === '1' ? '0' : '1';
        fireChange(sel);   // timeline.js wires the actual followMode update
      }
      e.preventDefault();
      break;
    }

    case ' ':              // Space — play / pause
    case 'Spacebar': {     // legacy IE/Edge name, harmless to also accept
      // Take focus off whatever button was last clicked so the browser's
      // own Space-activates-button behaviour doesn't double-fire.
      if (document.activeElement && document.activeElement !== document.body) {
        document.activeElement.blur();
      }
      document.getElementById('btn-play').click();
      e.preventDefault();
      break;
    }

    case '0':
      document.getElementById('btn-reset').click();
      e.preventDefault();
      break;

    case '1': case '2': case '3': case '4': case '5': case '6': {
      const value = SPEED_KEYS[parseInt(k, 10) - 1];
      const sel   = document.getElementById('sel-speed');
      if (sel && value !== undefined) {
        sel.value = value;
        fireChange(sel);   // restarts play interval if currently playing
      }
      e.preventDefault();
      break;
    }

    case '?':                // shift-/ on most layouts
    case '/':                // also accept plain / for convenience
      toggleKeysPanel();
      e.preventDefault();
      break;

    case 'Escape':           // close cheatsheet (and any open panels)
      toggleKeysPanel(false);
      // Don't preventDefault — let Escape still close native dialogs etc.
      break;
  }
});


// ── keyup + blur ────────────────────────────────────────────────

window.addEventListener('keyup', e => {
  const k = e.key.length === 1 ? e.key.toLowerCase() : e.key;
  if ('wasdqe'.includes(k)) heldKeys.delete(k);
});

// Alt-tab / focus loss leaves browsers in inconsistent keyup states.
// Clear held keys on blur so movement doesn't keep going invisibly.
window.addEventListener('blur', () => heldKeys.clear());


// ── Per-frame movement tick (called from main.js animate loop) ──

const _fwd   = new THREE.Vector3();
const _right = new THREE.Vector3();
const _up    = new THREE.Vector3(0, 1, 0);

export function tickCamera() {
  if (heldKeys.size === 0) return;

  // Movement speed scales with zoom distance — same convention as the
  // existing mouse-pan path. Tuned so a held key crosses ~10 kLY/sec at
  // a typical mid-zoom (r ≈ 9000) and stays sane at very close zoom.
  const v = orbit.sph.r * 0.02;

  // Forward = camera direction projected onto the galactic plane (Y=0).
  // Keeps W/S on the map plane regardless of camera tilt.
  camera.getWorldDirection(_fwd);
  _fwd.y = 0;
  if (_fwd.lengthSq() < 1e-6) _fwd.set(0, 0, -1);
  _fwd.normalize();

  // Right = forward × world-up (Y), already in the galactic plane.
  _right.crossVectors(_fwd, camera.up).normalize();

  if (heldKeys.has('w')) orbit.target.addScaledVector(_fwd,    v);
  if (heldKeys.has('s')) orbit.target.addScaledVector(_fwd,   -v);
  if (heldKeys.has('d')) orbit.target.addScaledVector(_right,  v);
  if (heldKeys.has('a')) orbit.target.addScaledVector(_right, -v);
  if (heldKeys.has('q')) orbit.target.addScaledVector(_up,     v);
  if (heldKeys.has('e')) orbit.target.addScaledVector(_up,    -v);

  orbit.update();
}
