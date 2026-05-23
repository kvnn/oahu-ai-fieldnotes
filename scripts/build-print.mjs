import { execFileSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';

import { PRINT_BUILD_ID_ENV, printBuildId, printBuildManifest } from './print-filenames.mjs';

const buildId = printBuildId();
const env = {
  ...process.env,
  [PRINT_BUILD_ID_ENV]: buildId,
};
const manifestPath = 'dist/print-build.json';

function writeManifest(extra = {}) {
  mkdirSync('dist', { recursive: true });
  writeFileSync(
    manifestPath,
    `${JSON.stringify({ ...printBuildManifest(buildId), ...extra }, null, 2)}\n`,
    'utf8',
  );
}

writeManifest({ status: 'started' });

for (const scriptName of ['build:cover', 'build:interior']) {
  execFileSync('npm', ['run', scriptName], {
    env,
    stdio: 'inherit',
  });
}

writeManifest({ status: 'completed', completedAt: new Date().toISOString() });

const manifest = printBuildManifest(buildId);
console.log(`print outputs: ${manifest.outputPaths.cover} ${manifest.outputPaths.interior}`);
