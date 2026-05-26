import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';

const outputPath = join('dist', 'generated-book', 'cover.html');
const mediaManifestPath = join('design', 'media', 'oahu-vol-1.toml');
const renderAssetPrefix = '../../';

function parseTomlValue(value) {
  const trimmed = value.trim();
  if (trimmed === 'true') return true;
  if (trimmed === 'false') return false;
  if (trimmed.startsWith('"') && trimmed.endsWith('"')) {
    return trimmed.slice(1, -1);
  }
  return trimmed;
}

function loadMediaManifest() {
  if (!existsSync(mediaManifestPath)) return [];
  const specs = [];
  let current = null;
  for (const rawLine of readFileSync(mediaManifestPath, 'utf8').split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#')) continue;
    if (line === '[[media]]') {
      current = {};
      specs.push(current);
      continue;
    }
    if (!current) continue;
    const match = line.match(/^([A-Za-z0-9_]+)\s*=\s*(.+)$/);
    if (!match) continue;
    current[match[1]] = parseTomlValue(match[2]);
  }
  return specs;
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('"', '&quot;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;');
}

function coverMediaHtml(slot) {
  return loadMediaManifest()
    .filter((spec) => spec.enabled !== false && spec.slot === slot)
    .map((spec) => {
      const treatmentClass = String(spec.treatment || 'cover_image').replaceAll('_', '-');
      const position = spec.position || 'bottom_right';
      const scale = spec.scale || 'medium';
      const decorative = spec.decorative !== false;
      const hidden = decorative ? ' aria-hidden="true"' : '';
      const alt = decorative ? '' : spec.alt_text || '';
      return [
        `<figure class="cover-media ${escapeHtml(treatmentClass)} cover-media-position-${escapeHtml(position)} cover-media-scale-${escapeHtml(scale)}" data-media-id="${escapeHtml(spec.id)}" data-media-slot="${escapeHtml(slot)}"${hidden}>`,
        `  <img src="${escapeHtml(renderAssetPrefix + spec.asset_path)}" alt="${escapeHtml(alt)}">`,
        '</figure>',
      ].join('\n');
    })
    .join('\n');
}

const coverFrontMedia = coverMediaHtml('cover_front');

const html = `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>O'ahu A.I. Field Notes Cover</title>
  </head>
  <body>
    <main class="cover-wrap" aria-label="O'ahu A.I. Field Notes cover wrap">
      <section class="cover-panel cover-back" aria-label="Back cover">
        <p class="cover-back-mark">O'AHU A.I. FIELD NOTES</p>
        <p class="cover-back-symbol">&oplus;</p>
      </section>
      <section class="cover-spine" aria-label="Spine">
        <p class="cover-spine-title">O'ahu A.I. | Field Notes | Volume 01</p>
      </section>
      <section class="cover-panel cover-front" aria-label="Front cover">
        <header class="cover-topline">
          <span>O'AHU A.I.</span>
          <span>VOL. 01</span>
        </header>
        <div class="cover-rule"></div>
        ${coverFrontMedia}
        <div class="cover-title-block">
          <h1>O'ahu A.I.</h1>
          <div class="cover-accent-rule"></div>
          <p class="cover-years">FIELD NOTES | 2023 - 2026</p>
          <p class="cover-tagline"></p>
        </div>
        <footer class="cover-footer">
          <span>EDITION / 200</span>
          <span>&oplus;</span>
        </footer>
      </section>
    </main>
  </body>
</html>
`;

mkdirSync(dirname(outputPath), { recursive: true });
writeFileSync(outputPath, html, 'utf8');
