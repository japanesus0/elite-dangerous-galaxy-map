// Static cross-reference of ESM imports/EXP across the module graph.
// Run inside docker as:
//   docker run --rm -v "<absolute-path-to-static/js>:/js" node:20-alpine \
//       node /js/../tests/check_imports.js
// Or, mounted at /work, run `node tests/check_imports.js /work/static/js`.
const fs   = require('fs');
const path = require('path');

const dir = process.argv[2] || '/js';
const files = fs.readdirSync(dir).filter(f => f.endsWith('.js'));

const EXP = {};
for (const f of files) {
  const src = fs.readFileSync(path.join(dir, f), 'utf8');
  const names = new Set();
  for (const m of src.matchAll(/export\s+(?:const|let|var|function|class|async\s+function)\s+([A-Za-z_$][\w$]*)/g)) names.add(m[1]);
  for (const m of src.matchAll(/export\s*\{([^}]+)\}/g)) {
    for (const part of m[1].split(',')) {
      const seg = part.trim().split(/\s+as\s+/);
      const exported = (seg[1] || seg[0]).trim();
      if (exported) names.add(exported);
    }
  }
  EXP[f] = names;
}

let problems = 0;
for (const f of files) {
  const src = fs.readFileSync(path.join(dir, f), 'utf8');
  // import { … } from './foo.js'
  for (const m of src.matchAll(/import\s+\{([^}]+)\}\s+from\s+['"]\.\/([\w-]+)\.js['"]/g)) {
    const target = m[2] + '.js';
    if (!EXP[target]) {
      console.log(`x ${f}: imports from missing file ./${target}`);
      problems++; continue;
    }
    for (const part of m[1].split(',')) {
      const seg = part.trim().split(/\s+as\s+/);
      const importName = seg[0].trim();
      if (!importName) continue;
      if (!EXP[target].has(importName)) {
        console.log(`x ${f}: imports { ${importName} } from ./${target} -- not exported`);
        problems++;
      }
    }
  }
  // import * as ns from './foo.js'  (just verify file exists)
  for (const m of src.matchAll(/import\s+\*\s+as\s+\w+\s+from\s+['"]\.\/([\w-]+)\.js['"]/g)) {
    const target = m[1] + '.js';
    if (!EXP[target]) {
      console.log(`x ${f}: namespace-imports from missing file ./${target}`);
      problems++;
    }
  }
}

if (problems === 0) console.log('OK All cross-module imports resolve.');
else                console.log(`\n${problems} unresolved import(s).`);
process.exit(problems === 0 ? 0 : 1);
