import { existsSync, readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';

const PRINT_BUILD_MANIFEST = 'dist/print-build.json';
const DEFAULT_INTERIOR_PATH = 'dist/interior.pdf';
const DEFAULT_COVER_PATH = 'dist/cover.pdf';
const EXPECTED_INTERIOR_PAGES = 68;
const EXPECTED_COVER_WIDTH_PT = 823.68;
const EXPECTED_COVER_HEIGHT_PT = 630.72;
const SIZE_TOLERANCE_PT = 1.2;

function printOutputPaths() {
  if (!existsSync(PRINT_BUILD_MANIFEST)) {
    return {
      interior: DEFAULT_INTERIOR_PATH,
      cover: DEFAULT_COVER_PATH,
    };
  }
  const manifest = JSON.parse(readFileSync(PRINT_BUILD_MANIFEST, 'utf8'));
  return {
    interior: manifest.outputPaths?.interior || DEFAULT_INTERIOR_PATH,
    cover: manifest.outputPaths?.cover || DEFAULT_COVER_PATH,
  };
}

const { interior: INTERIOR_PATH, cover: COVER_PATH } = printOutputPaths();

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

function assertCoverSize(path) {
  const info = run('pdfinfo', ['-box', path]);
  const match = info.match(/^Page size:\s+([\d.]+) x ([\d.]+) pts/m);
  if (!match) {
    fail(`could not read page size for ${path}`);
    return;
  }
  const width = Number(match[1]);
  const height = Number(match[2]);
  if (
    Math.abs(width - EXPECTED_COVER_WIDTH_PT) > SIZE_TOLERANCE_PT ||
    Math.abs(height - EXPECTED_COVER_HEIGHT_PT) > SIZE_TOLERANCE_PT
  ) {
    fail(
      `${path} size ${width} x ${height} pts does not match expected ` +
        `${EXPECTED_COVER_WIDTH_PT} x ${EXPECTED_COVER_HEIGHT_PT} pts`,
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

const pages = pageCount(INTERIOR_PATH);
if (pages !== EXPECTED_INTERIOR_PAGES) {
  fail(`${INTERIOR_PATH} has ${pages} pages; expected ${EXPECTED_INTERIOR_PAGES}`);
}

assertCoverSize(COVER_PATH);
assertDisplayFontEmbedded(INTERIOR_PATH);
assertDisplayFontEmbedded(COVER_PATH);
assertPdfx4(INTERIOR_PATH);
assertPdfx4(COVER_PATH);

if (!process.exitCode) {
  console.log('verify:print passed');
}
