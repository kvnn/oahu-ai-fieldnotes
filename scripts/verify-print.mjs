import { existsSync, readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';

const PRINT_BUILD_MANIFEST = 'dist/print-build.json';
const DEFAULT_COVER_FRONT_PATH = 'dist/01_oahu-ai-field-notes_outer-front-cover.pdf';
const DEFAULT_COVER_BACK_PATH = 'dist/02_oahu-ai-field-notes_outer-back-cover.pdf';
const DEFAULT_COVER_SPINE_PATH = 'dist/03_oahu-ai-field-notes_spine.pdf';
const DEFAULT_INTERIOR_PATH = 'dist/04_oahu-ai-field-notes_inner-pages.pdf';
const EXPECTED_INTERIOR_PAGES = 68;
const EXPECTED_COVER_PANEL_WIDTH_PT = 414.72;
const EXPECTED_COVER_SPINE_WIDTH_PT = 12.96;
const EXPECTED_COVER_HEIGHT_PT = 630.72;
const SIZE_TOLERANCE_PT = 1.2;

function printOutputPaths() {
  if (!existsSync(PRINT_BUILD_MANIFEST)) {
    return {
      interior: DEFAULT_INTERIOR_PATH,
      coverFront: DEFAULT_COVER_FRONT_PATH,
      coverBack: DEFAULT_COVER_BACK_PATH,
      coverSpine: DEFAULT_COVER_SPINE_PATH,
      coverSource: null,
    };
  }
  const manifest = JSON.parse(readFileSync(PRINT_BUILD_MANIFEST, 'utf8'));
  return {
    interior: manifest.outputPaths?.interior || DEFAULT_INTERIOR_PATH,
    coverFront: manifest.outputPaths?.coverFront || DEFAULT_COVER_FRONT_PATH,
    coverBack: manifest.outputPaths?.coverBack || DEFAULT_COVER_BACK_PATH,
    coverSpine: manifest.outputPaths?.coverSpine || DEFAULT_COVER_SPINE_PATH,
    coverSource: manifest.outputPaths?.coverSource || null,
  };
}

const {
  interior: INTERIOR_PATH,
  coverFront: COVER_FRONT_PATH,
  coverBack: COVER_BACK_PATH,
  coverSpine: COVER_SPINE_PATH,
  coverSource: COVER_SOURCE_PATH,
} = printOutputPaths();

function run(command, args) {
  return execFileSync(command, args, {
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'pipe'],
  });
}

function fail(message) {
  console.error(`verify:print failed: ${message}`);
  process.exitCode = 1;
}

function warn(message) {
  console.warn(`verify:print warning: ${message}`);
}

function assertPdfx4(path) {
  const bytes = readFileSync(path);
  const text = bytes.toString('latin1');
  if (!text.includes('PDF/X-4') && !text.includes('PDF/X-4p')) {
    fail(`${path} is not marked as PDF/X-4`);
  }
}

function pageCount(path) {
  const info = run('pdfinfo', [path]);
  const match = info.match(/^Pages:\s+(\d+)/m);
  if (!match) {
    fail(`could not read page count for ${path}`);
    return 0;
  }
  return Number(match[1]);
}

function assertPdfSize(path, expectedWidth, expectedHeight) {
  const info = run('pdfinfo', ['-box', path]);
  const match = info.match(/^Page size:\s+([\d.]+) x ([\d.]+) pts/m);
  if (!match) {
    fail(`could not read page size for ${path}`);
    return;
  }
  const width = Number(match[1]);
  const height = Number(match[2]);
  if (
    Math.abs(width - expectedWidth) > SIZE_TOLERANCE_PT ||
    Math.abs(height - expectedHeight) > SIZE_TOLERANCE_PT
  ) {
    fail(
      `${path} size ${width} x ${height} pts does not match expected ` +
        `${expectedWidth} x ${expectedHeight} pts`,
    );
  }
}

function assertDisplayFontEmbedded(path) {
  const fonts = run('pdffonts', [path]);
  const cormorantLines = fonts
    .split('\n')
    .filter((line) => /Cormorant/i.test(line));
  if (cormorantLines.length === 0) {
    fail(`Cormorant display font is missing from ${path}`);
    return;
  }
  for (const line of cormorantLines) {
    const fontFlags = line.match(/\s+(yes|no)\s+(yes|no)\s+(yes|no)\s+\d+\s+\d+\s*$/);
    if (!fontFlags) {
      fail(`could not parse font embedding flags for ${path}: ${line}`);
      continue;
    }
    const embedded = fontFlags[1];
    if (embedded !== 'yes') {
      fail(`display font is not embedded in ${path}: ${line}`);
    }
  }
}

function assertFlattenedCover(path) {
  const bytes = readFileSync(path);
  const text = bytes.toString('latin1');
  for (const marker of ['/SMask', '/Transparency', '/OCProperties', '/OCG']) {
    if (text.includes(marker)) {
      fail(`${path} still contains ${marker}; cover is not fully flattened`);
    }
  }
}

function assertCoverImagePpi(path) {
  const images = run('pdfimages', ['-list', path]);
  const imageRows = images
    .split('\n')
    .filter((line) => /^\s*\d+\s+\d+\s+image\s+/.test(line));
  if (imageRows.length !== 1) {
    fail(`${path} should contain exactly one flattened image; found ${imageRows.length}`);
    return;
  }
  const parts = imageRows[0].trim().split(/\s+/);
  const xPpi = Number(parts[12]);
  const yPpi = Number(parts[13]);
  if (xPpi < 300 || yPpi < 300) {
    fail(`${path} flattened cover image is ${xPpi} x ${yPpi} ppi; expected at least 300`);
  }
}

const pages = pageCount(INTERIOR_PATH);
if (pages !== EXPECTED_INTERIOR_PAGES) {
  warn(`${INTERIOR_PATH} has ${pages} pages; expected ${EXPECTED_INTERIOR_PAGES}`);
}

const coverParts = [
  [COVER_FRONT_PATH, EXPECTED_COVER_PANEL_WIDTH_PT, EXPECTED_COVER_HEIGHT_PT],
  [COVER_BACK_PATH, EXPECTED_COVER_PANEL_WIDTH_PT, EXPECTED_COVER_HEIGHT_PT],
  [COVER_SPINE_PATH, EXPECTED_COVER_SPINE_WIDTH_PT, EXPECTED_COVER_HEIGHT_PT],
];

for (const [path, expectedWidth, expectedHeight] of coverParts) {
  assertPdfSize(path, expectedWidth, expectedHeight);
  assertFlattenedCover(path);
  assertCoverImagePpi(path);
  assertPdfx4(path);
}
assertDisplayFontEmbedded(INTERIOR_PATH);
if (COVER_SOURCE_PATH && existsSync(COVER_SOURCE_PATH)) {
  assertDisplayFontEmbedded(COVER_SOURCE_PATH);
}
assertPdfx4(INTERIOR_PATH);

if (!process.exitCode) {
  console.log('verify:print passed');
}
