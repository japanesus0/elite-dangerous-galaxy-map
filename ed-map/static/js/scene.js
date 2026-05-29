// ═══════════════════════════════════════════════════════════════
// scene.js — Three.js scene, camera, renderer, orbit controls,
//            starfield, milky-way disk, landmark markers (Sol, SgrA*, Colonia),
//            and the shared circular glow texture used by halos.
// ───────────────────────────────────────────────────────────────
// THREE is loaded as a global UMD script before any module runs.
// ═══════════════════════════════════════════════════════════════

import { SOL_POS, SGRA_POS, COLONIA_POS, COLOR } from './constants.js';

// ── Scene + camera + renderer ───────────────────────────────────

export const scene = new THREE.Scene();
scene.fog = new THREE.FogExp2(0x000008, 0.000008);

export const camera = new THREE.PerspectiveCamera(55, innerWidth / innerHeight, 0.5, 150000);
camera.position.set(0, 3500, 9000);

export const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(innerWidth, innerHeight);
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.autoClear = false;   // We manage clear manually to enable scissor sub-scene
document.body.appendChild(renderer.domElement);

// Some other modules need to know if a click landed in the detail panel
// rather than on the canvas — we expose a tiny lock that they can set/read.
export const clickLock = { detail: false };


// ── Orbit controls (custom — no OrbitControls dependency) ───────

export const orbit = {
  target:  new THREE.Vector3(0, 0, 0),
  sph:     { r: 9000, phi: 1.1, theta: -0.3 },

  _drag:   false,
  _pan:    false,
  _last:   { x: 0, y: 0 },

  update() {
    const { r, phi, theta } = this.sph;
    const sinPhi = Math.sin(phi), cosPhi = Math.cos(phi);
    camera.position.set(
      this.target.x + r * sinPhi * Math.sin(theta),
      this.target.y + r * cosPhi,
      this.target.z + r * sinPhi * Math.cos(theta),
    );
    camera.lookAt(this.target);
  },

  onMouseDown(e) {
    if (e.button === 0) { this._drag = true; this._pan = false; }
    if (e.button === 2) { this._pan  = true; this._drag = false; }
    this._last = { x: e.clientX, y: e.clientY };
    e.preventDefault();
  },
  onMouseMove(e) {
    const dx = e.clientX - this._last.x;
    const dy = e.clientY - this._last.y;
    this._last = { x: e.clientX, y: e.clientY };

    if (this._drag) {
      this.sph.theta -= dx * 0.004;
      this.sph.phi    = Math.max(0.05, Math.min(Math.PI - 0.05, this.sph.phi + dy * 0.004));
    }
    if (this._pan) {
      // Pan perpendicular to view direction, proportional to distance
      const scale = this.sph.r * 0.001;
      const right = new THREE.Vector3();
      const up    = new THREE.Vector3();
      camera.getWorldDirection(new THREE.Vector3()); // ensure matrix updated
      right.crossVectors(camera.getWorldDirection(new THREE.Vector3()), camera.up).normalize();
      up.copy(camera.up).normalize();
      this.target.addScaledVector(right, -dx * scale);
      this.target.addScaledVector(up,     dy * scale);
    }
    this.update();
  },
  onMouseUp()  { this._drag = false; this._pan = false; },
  onWheel(e) {
    const factor = e.deltaY > 0 ? 1.12 : 0.88;
    this.sph.r = Math.max(50, Math.min(80000, this.sph.r * factor));
    this.update();
    e.preventDefault();
  },
};

renderer.domElement.addEventListener('mousedown',   e => { if (!clickLock.detail) orbit.onMouseDown(e); }, { passive: false });
renderer.domElement.addEventListener('contextmenu', e => e.preventDefault());
window.addEventListener('mousemove',  e  => orbit.onMouseMove(e));
window.addEventListener('mouseup',    () => orbit.onMouseUp());
renderer.domElement.addEventListener('wheel', e => orbit.onWheel(e), { passive: false });
orbit.update();


// ── Starfield background ────────────────────────────────────────

function buildStarfield() {
  const N   = 22000;
  const pos = new Float32Array(N * 3);
  const col = new Float32Array(N * 3);
  const rng = () => Math.random();

  for (let i = 0; i < N; i++) {
    const R     = 65000 + rng() * 18000;
    const theta = rng() * Math.PI * 2;
    // Concentrate stars in galactic plane (low |phi|) for milky-way effect
    const phi   = rng() < 0.65
      ? (rng() - 0.5) * 0.35
      : (rng() - 0.5) * Math.PI;

    pos[i*3]   = R * Math.cos(phi) * Math.cos(theta);
    pos[i*3+1] = R * Math.sin(phi);
    pos[i*3+2] = R * Math.cos(phi) * Math.sin(theta);

    // Colour: mostly white-blue, some warm
    const t = rng();
    if (t < 0.65) {
      const v = 0.5 + rng() * 0.5;
      col[i*3] = v * 0.85; col[i*3+1] = v * 0.9; col[i*3+2] = v;
    } else if (t < 0.82) {
      col[i*3] = 0.6; col[i*3+1] = 0.75; col[i*3+2] = 1.0;
    } else {
      col[i*3] = 1.0; col[i*3+1] = 0.85; col[i*3+2] = 0.5;
    }
  }

  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  geo.setAttribute('color',    new THREE.BufferAttribute(col, 3));

  const mat = new THREE.PointsMaterial({
    size: 1.2, vertexColors: true,
    sizeAttenuation: false,
    transparent: true, opacity: 0.75,
    depthWrite: false,
  });
  return new THREE.Points(geo, mat);
}

scene.add(buildStarfield());


// ── Milky-Way galaxy plane ──────────────────────────────────────
// Procedural galaxy rendered as a single flat plane in the XZ galactic
// plane, centered on the galactic centre (Sag A* position in ED coords).
// Uses a canvas texture so zero external assets are required.
// renderOrder -1 ensures it sits behind the jump-point cloud and starfield.

function _buildGalaxyCanvas() {
  const S   = 1024;
  const cv  = document.createElement('canvas');
  cv.width  = cv.height = S;
  const ctx = cv.getContext('2d');
  const cx  = S / 2, cy = S / 2;

  // ── 1. Diffuse disk background ──
  const disk = ctx.createRadialGradient(cx, cy, 0, cx, cy, S * 0.50);
  disk.addColorStop(0.00, 'rgba(255,228,160,0.90)');
  disk.addColorStop(0.06, 'rgba(245,215,155,0.72)');
  disk.addColorStop(0.14, 'rgba(210,200,210,0.48)');
  disk.addColorStop(0.28, 'rgba(170,175,230,0.28)');
  disk.addColorStop(0.46, 'rgba(145,155,225,0.16)');
  disk.addColorStop(0.65, 'rgba(115,135,218,0.07)');
  disk.addColorStop(0.84, 'rgba( 90,115,210,0.02)');
  disk.addColorStop(1.00, 'rgba( 70, 95,200,0.00)');
  ctx.fillStyle = disk;
  ctx.fillRect(0, 0, S, S);

  // ── 2. Spiral arms ──
  // Logarithmic spiral: r = 0.04 × e^(0.20 × t), t ∈ [0, 4π]
  // Two full wraps; 4 arms (2 major opposite + 2 minor offset).
  ctx.save();
  ctx.globalCompositeOperation = 'lighter';

  function drawArm(offsetAngle, alpha, width) {
    ctx.save();
    ctx.globalAlpha  = alpha;
    ctx.strokeStyle  = 'rgba(190, 205, 255, 1)';
    ctx.lineWidth    = S * width;
    ctx.lineCap      = 'round';
    ctx.lineJoin     = 'round';
    ctx.shadowBlur   = S * width * 1.5;
    ctx.shadowColor  = 'rgba(175, 190, 255, 0.75)';
    ctx.beginPath();
    let first = true;
    for (let t = 0.10; t <= Math.PI * 4.1; t += 0.016) {
      const r  = 0.04 * Math.exp(0.20 * t);
      if (r > 0.50) break;
      const a  = t + offsetAngle;
      const px = cx + r * S * Math.cos(a);
      const py = cy + r * S * Math.sin(a);
      if (first) { ctx.moveTo(px, py); first = false; }
      else ctx.lineTo(px, py);
    }
    ctx.stroke();
    ctx.restore();
  }

  drawArm(0.00,           0.58, 0.044);  // major arm A
  drawArm(Math.PI,        0.58, 0.044);  // major arm B (opposite)
  drawArm(Math.PI * 0.52, 0.36, 0.030);  // minor arm C
  drawArm(Math.PI * 1.52, 0.36, 0.030);  // minor arm D

  ctx.restore();

  // ── 3. Galactic bar ──
  ctx.save();
  ctx.globalCompositeOperation = 'lighter';
  const barGrad = ctx.createLinearGradient(cx - S*0.11, cy, cx + S*0.11, cy);
  barGrad.addColorStop(0.00, 'rgba(255,235,155,0.00)');
  barGrad.addColorStop(0.35, 'rgba(255,235,155,0.28)');
  barGrad.addColorStop(0.50, 'rgba(255,242,170,0.40)');
  barGrad.addColorStop(0.65, 'rgba(255,235,155,0.28)');
  barGrad.addColorStop(1.00, 'rgba(255,235,155,0.00)');
  ctx.fillStyle = barGrad;
  ctx.beginPath();
  ctx.ellipse(cx, cy, S * 0.11, S * 0.028, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();

  // ── 4. Galactic bulge ──
  const bulge = ctx.createRadialGradient(cx, cy, 0, cx, cy, S * 0.13);
  bulge.addColorStop(0.00, 'rgba(255,255,210,1.00)');
  bulge.addColorStop(0.22, 'rgba(255,240,160,0.88)');
  bulge.addColorStop(0.50, 'rgba(255,210,110,0.50)');
  bulge.addColorStop(0.80, 'rgba(255,180, 75,0.18)');
  bulge.addColorStop(1.00, 'rgba(255,155, 55,0.00)');
  ctx.fillStyle = bulge;
  ctx.fillRect(0, 0, S, S);

  // ── 5. Galactic core bright point ──
  const core = ctx.createRadialGradient(cx, cy, 0, cx, cy, S * 0.026);
  core.addColorStop(0.00, 'rgba(255,255,255,1.0)');
  core.addColorStop(0.40, 'rgba(255,248,215,0.9)');
  core.addColorStop(1.00, 'rgba(255,225,165,0.0)');
  ctx.fillStyle = core;
  ctx.fillRect(0, 0, S, S);

  return cv;
}

function buildMilkyWay() {
  const tex = new THREE.CanvasTexture(_buildGalaxyCanvas());
  const HALF = 58000;
  const geo  = new THREE.PlaneGeometry(HALF * 2, HALF * 2, 1, 1);
  const mat  = new THREE.MeshBasicMaterial({
    map:         tex,
    transparent: true,
    opacity:     0.30,
    depthWrite:  false,
    side:        THREE.DoubleSide,
    blending:    THREE.AdditiveBlending,
    fog:         false,
  });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.rotation.x = -Math.PI / 2;
  mesh.position.set(SGRA_POS.x, SGRA_POS.y - 5, SGRA_POS.z);
  mesh.renderOrder = -1;
  return mesh;
}

scene.add(buildMilkyWay());


// ── Shared circular glow texture (reused by landmarks + active halo) ──

export const glowTex = (() => {
  const sz  = 64;
  const cv  = document.createElement('canvas');
  cv.width  = cv.height = sz;
  const ctx = cv.getContext('2d');
  const g   = ctx.createRadialGradient(sz/2, sz/2, 0, sz/2, sz/2, sz/2);
  g.addColorStop(0.0,  'rgba(255,255,255,1.0)');
  g.addColorStop(0.25, 'rgba(255,255,255,0.7)');
  g.addColorStop(0.6,  'rgba(255,255,255,0.2)');
  g.addColorStop(1.0,  'rgba(255,255,255,0.0)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, sz, sz);
  return new THREE.CanvasTexture(cv);
})();


// ── Landmark markers (Sol, Sag A*, Colonia) ─────────────────────

function makeLandmark(pos, hex, radius = 8) {
  const geo  = new THREE.SphereGeometry(radius, 12, 12);
  const mat  = new THREE.MeshBasicMaterial({ color: hex });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.position.set(pos.x, pos.y, pos.z);
  return mesh;
}

function makeGlow(pos, hex, size = 120) {
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(
    new Float32Array([pos.x, pos.y, pos.z]), 3
  ));
  const mat = new THREE.PointsMaterial({
    color: hex, size,
    map: glowTex,
    sizeAttenuation: true,
    depthWrite: false,
    transparent: true,
    opacity: 0.7,
    alphaTest: 0.01,
  });
  return new THREE.Points(geo, mat);
}

scene.add(makeLandmark(SOL_POS,     COLOR.sol,     12));
scene.add(makeGlow    (SOL_POS,     COLOR.sol,     180));
scene.add(makeLandmark(SGRA_POS,    COLOR.sgra,    14));
scene.add(makeGlow    (SGRA_POS,    COLOR.sgra,    220));
scene.add(makeLandmark(COLONIA_POS, COLOR.colonia, 10));
scene.add(makeGlow    (COLONIA_POS, COLOR.colonia, 160));


// ── Resize handling for the main camera ─────────────────────────

window.addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
});
