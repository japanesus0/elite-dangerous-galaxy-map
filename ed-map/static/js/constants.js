// ═══════════════════════════════════════════════════════════════
// constants.js — pure constants and small formatters
// No DOM access, no THREE. Safe to import from anywhere.
// ═══════════════════════════════════════════════════════════════

// Sol is at the origin. Sag A* is here in ED galactic coords.
export const SOL_POS     = { x: 0,        y: 0,          z: 0 };
export const SGRA_POS    = { x: 25.22,    y: -20.91,     z: 25899.97 };
// Colonia — Jaques Station / Colonia / Animula Spires / Mosta-Murdoch Raceway
// SystemAddress 3238296097059. ED galactic coords (LY).
export const COLONIA_POS = { x: -9530.5,  y: -910.28125, z: 19808.125 };

// Color map by jump type (Three.js hex)
export const COLOR = {
  transit:   0x1e6bbf,
  discovery: 0x00e676,
  earthlike: 0x00b0ff,
  bounty:    0xff1744,
  mixed:     0xffab00,
  sol:       0xffd600,
  sgra:      0xff6d00,
  colonia:   0xe040fb,   // bright magenta — human outpost, distinct from Sol/SgrA*
};

// ── Playback speed config ──
// [interval_ms, steps_per_tick]  — 1× = 1 jump per second
export const SPEED_CFG = {
  '0.25': [4000, 1],   // 1 jump every 4 s
  '0.5':  [2000, 1],   // 1 jump every 2 s
  '1':    [1000, 1],   // 1 jump / s
  '5':    [200,  1],   // 5 jumps / s
  '20':   [50,   1],   // 20 jumps / s
  '100':  [50,   5],   // 100 jumps / s
};

// ── Ship internal-key → display name lookup ──
export const SHIP_DISPLAY_NAMES = {
  'sidewinder':            'Sidewinder',
  'eagle_mkii':            'Eagle Mk II',
  'eagle':                 'Eagle Mk II',
  'imperial_eagle':        'Imperial Eagle',
  'cobra_mkiii':           'Cobra Mk III',
  'cobra_mkiv':            'Cobra Mk IV',
  'viper':                 'Viper Mk III',
  'viper_mkiv':            'Viper Mk IV',
  'asp':                   'Asp Explorer',
  'asp_scout':             'Asp Scout',
  'adder':                 'Adder',
  'hauler':                'Hauler',
  'diamondback':           'Diamondback Explorer',
  'diamondbackscout':      'Diamondback Scout',
  'vulture':               'Vulture',
  'ferdelance':            'Fer-de-Lance',
  'mamba':                 'Mamba',
  'krait_mkii':            'Krait Mk II',
  'krait_light':           'Krait Phantom',
  'python':                'Python',
  'anaconda':              'Anaconda',
  'cutter':                'Imperial Cutter',
  'federation_corvette':   'Federal Corvette',
  'federation_dropship':   'Federal Dropship',
  'federation_gunship':    'Federal Gunship',
  'alliance_chieftain':    'Alliance Chieftain',
  'alliance_crusader':     'Alliance Crusader',
  'alliance_challenger':   'Alliance Challenger',
  'type6':                 'Type-6 Transporter',
  'type7':                 'Type-7 Transporter',
  'type9':                 'Type-9 Heavy',
  'type10':                'Type-10 Defender',
  'type9_military':        'Type-10 Defender',
  'dolphin':               'Dolphin',
  'orca':                  'Orca',
  'belugaliner':           'Beluga Liner',
};


// ── Compact number formatters (used by stats bar, charts, panels) ──

export function fmtK(n) {
  n = Number(n);
  if (n >= 1e9) return (n / 1e9).toFixed(1) + 'B';
  if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
  if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K';
  return Math.round(n).toLocaleString();
}

// Bounty / credits formatter — slightly more precision at large scale
export function fmtCr(n) {
  n = Number(n);
  if (n >= 1e9) return (n / 1e9).toFixed(2) + 'B';
  if (n >= 1e6) return (n / 1e6).toFixed(2) + 'M';
  if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K';
  return n.toLocaleString();
}
