// ═══════════════════════════════════════════════════════════════
// main.js — entry point
// ───────────────────────────────────────────────────────────────
//   1. Pull together every module (their top-level code wires
//      DOM listeners, builds the scene, etc.).
//   2. Kick off data load.
//   3. Run the render loop (main scene + ship sub-scene).
// ═══════════════════════════════════════════════════════════════

import { state } from './state.js';
import { camera, renderer, scene, orbit } from './scene.js';
import { activeHaloMat } from './jumps.js';
import { maybeCheckHover } from './panels.js';
// shipMeshGroup is reassigned inside ship-viewer.js when the active ship
// changes, so we must read it through the namespace each frame to see the
// live binding (a destructured import would also work, but this makes the
// intent clearer at the call site).
import { shipScene, shipCamera } from './ship-viewer.js';
import * as shipViewer from './ship-viewer.js';
import { loadData, followTarget } from './data.js';
// keyboard.js installs its listeners at top level when imported; we also
// pull tickCamera() to apply held movement keys each frame.
import { tickCamera } from './keyboard.js';

// ── Active-jump label projection ────────────────────────────────

const _ajlVec = new THREE.Vector3();

function positionActiveJumpLabel() {
  const el = document.getElementById('active-jump-label');
  if (!el) return;
  const j = state.jumpsData[state.currentIdx];
  if (!j || !state.jumpsData.length) { el.style.display = 'none'; return; }

  // Respect the lastN filter — if the current dot is outside the visible
  // window the label would look misleading.
  if (state.lastNJumps > 0) {
    const drawStart = Math.max(0, state.currentIdx + 1 - state.lastNJumps);
    if (state.currentIdx < drawStart) { el.style.display = 'none'; return; }
  }

  _ajlVec.set(j.x, j.y, j.z).project(camera);
  if (_ajlVec.z > 1) { el.style.display = 'none'; return; }   // behind camera

  const x = (_ajlVec.x *  0.5 + 0.5) * innerWidth;
  const y = (_ajlVec.y * -0.5 + 0.5) * innerHeight;

  // Offscreen margin — hide rather than plaster the label at the edge
  if (x < -40 || x > innerWidth + 40 || y < -40 || y > innerHeight + 40) {
    el.style.display = 'none'; return;
  }
  el.style.left    = x + 'px';
  el.style.top     = y + 'px';
  el.style.display = 'block';
}


// ── Main render loop ────────────────────────────────────────────

function animate() {
  requestAnimationFrame(animate);

  // ── Follow-cam: smoothly track the current jump point ──
  // First-press of any movement key in keyboard.js disables follow-cam,
  // so the two never fight over orbit.target in the same frame.
  if (state.followMode && state.jumpsData.length && state.currentIdx >= 0) {
    const j = state.jumpsData[state.currentIdx];
    followTarget.set(j.x, j.y, j.z);
    // 0.06 → silky smooth; raise toward 1.0 for instant snap
    orbit.target.lerp(followTarget, 0.06);
    orbit.update();
  }

  // Apply any held WASD/QE movement (no-op if no keys held)
  tickCamera();

  // Hover check (panels.js handles throttling + follow-cam skip)
  maybeCheckHover();

  // Project current jump's world pos → screen and reposition label
  positionActiveJumpLabel();

  // ── Zoom-aware halo sizing ──
  // Use orbit distance as the zoom proxy so the halo reads the same
  // angular size at any zoom. Clamp so it never collapses or explodes.
  if (activeHaloMat) {
    const r = orbit.sph.r;                 // 50 .. 80000 per onWheel clamp
    const desired = Math.max(8, Math.min(600, r * 0.012));
    if (activeHaloMat.size !== desired) activeHaloMat.size = desired;
  }

  // ── Main scene ──
  renderer.clear();
  renderer.render(scene, camera);

  // ── Ship sub-scene (bottom-left inset via scissor) ──
  const svEl = document.getElementById('ship-viewer-canvas-area');
  if (svEl) {
    const rect = svEl.getBoundingClientRect();
    if (rect.width > 0 && rect.height > 0) {
      const sx = rect.left;
      const sy = innerHeight - rect.bottom;
      renderer.setScissorTest(true);
      renderer.setScissor (sx, sy, rect.width, rect.height);
      renderer.setViewport(sx, sy, rect.width, rect.height);
      renderer.clearDepth();
      // Spin the wireframe around its Y axis a bit each frame
      if (shipViewer.shipMeshGroup) shipViewer.shipMeshGroup.rotation.y += 0.008;
      renderer.render(shipScene, shipCamera);
      renderer.setScissorTest(false);
      renderer.setViewport(0, 0, innerWidth, innerHeight);
    }
  }
}


// ── Boot ────────────────────────────────────────────────────────

loadData().catch(err => {
  document.getElementById('loading-status').textContent = 'Error: ' + err.message;
  console.error(err);
});

animate();
