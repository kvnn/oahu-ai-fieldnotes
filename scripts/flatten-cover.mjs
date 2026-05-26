import { execFileSync } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { PDFDocument } from 'pdf-lib';

import { printOutputPaths } from './print-filenames.mjs';

const COVER_HEIGHT_PT = 630.72;
const COVER_BLEED_PT = 9.36;
const COVER_PANEL_TRIM_WIDTH_PT = 396;
const COVER_PANEL_WIDTH_PT = COVER_PANEL_TRIM_WIDTH_PT + COVER_BLEED_PT * 2;
const COVER_SPINE_WIDTH_PT = 12.96;
const FLATTEN_DPI = 300;
const LEGACY_FULL_SPREAD_UPLOAD_PATH = 'dist/01_oahu-ai-field-notes_front-back-spine-cover.pdf';

const printPaths = printOutputPaths();

async function flattenCover() {
  const workDir = mkdtempSync(join(tmpdir(), 'fieldnotes-cover-flatten-'));

  try {
    const coverParts = [
      {
        label: 'Outer Front Cover',
        path: printPaths.coverFront,
        rasterPrefix: join(workDir, 'front'),
        width: COVER_PANEL_WIDTH_PT,
        pixelCrop: { x: 1704, y: 0, width: 1728, height: 2628 },
        trimBox: {
          x: COVER_BLEED_PT,
          y: COVER_BLEED_PT,
          width: COVER_PANEL_TRIM_WIDTH_PT,
          height: COVER_HEIGHT_PT - COVER_BLEED_PT * 2,
        },
      },
      {
        label: 'Outer Back Cover',
        path: printPaths.coverBack,
        rasterPrefix: join(workDir, 'back'),
        width: COVER_PANEL_WIDTH_PT,
        pixelCrop: { x: 0, y: 0, width: 1728, height: 2628 },
        trimBox: {
          x: COVER_BLEED_PT,
          y: COVER_BLEED_PT,
          width: COVER_PANEL_TRIM_WIDTH_PT,
          height: COVER_HEIGHT_PT - COVER_BLEED_PT * 2,
        },
      },
      {
        label: 'Spine',
        path: printPaths.coverSpine,
        rasterPrefix: join(workDir, 'spine'),
        width: COVER_SPINE_WIDTH_PT,
        pixelCrop: { x: 1689, y: 0, width: 54, height: 2628 },
        trimBox: {
          x: 0,
          y: COVER_BLEED_PT,
          width: COVER_SPINE_WIDTH_PT,
          height: COVER_HEIGHT_PT - COVER_BLEED_PT * 2,
        },
      },
    ];

    for (const part of coverParts) {
      const rasterPath = renderRasterPart(part);
      await writeCoverPart(part, readFileSync(rasterPath));
      console.log(`flattened ${part.label.toLowerCase()} output: ${part.path}`);
    }
    if (existsSync(LEGACY_FULL_SPREAD_UPLOAD_PATH)) {
      rmSync(LEGACY_FULL_SPREAD_UPLOAD_PATH, { force: true });
    }
  } finally {
    rmSync(workDir, { recursive: true, force: true });
  }
}

function renderRasterPart(part) {
  execFileSync(
    'pdftoppm',
    [
      '-png',
      '-r',
      String(FLATTEN_DPI),
      '-singlefile',
      '-x',
      String(part.pixelCrop.x),
      '-y',
      String(part.pixelCrop.y),
      '-W',
      String(part.pixelCrop.width),
      '-H',
      String(part.pixelCrop.height),
      printPaths.coverSource,
      part.rasterPrefix,
    ],
    { stdio: 'inherit' },
  );
  return `${part.rasterPrefix}.png`;
}

async function writeCoverPart(part, rasterBytes) {
  const pdf = await PDFDocument.create();
  pdf.setTitle(`O'ahu A.I. Field Notes ${part.label}`);
  pdf.setAuthor('Kevin Nguyen');
  pdf.setProducer('Oahu AI Field Notes print pipeline');
  pdf.setCreator('Oahu AI Field Notes flatten-cover');

  const page = pdf.addPage([part.width, COVER_HEIGHT_PT]);
  page.setMediaBox(0, 0, part.width, COVER_HEIGHT_PT);
  page.setCropBox(0, 0, part.width, COVER_HEIGHT_PT);
  page.setBleedBox(0, 0, part.width, COVER_HEIGHT_PT);
  page.setTrimBox(
    part.trimBox.x,
    part.trimBox.y,
    part.trimBox.width,
    part.trimBox.height,
  );
  page.setArtBox(0, 0, part.width, COVER_HEIGHT_PT);

  const raster = await pdf.embedPng(rasterBytes);
  page.drawImage(raster, {
    x: 0,
    y: 0,
    width: part.width,
    height: COVER_HEIGHT_PT,
  });

  writeFileSync(part.path, await pdf.save());
}

flattenCover().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
