import { execFileSync } from 'node:child_process';
import { mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { PDFDocument } from 'pdf-lib';

import { printOutputPaths } from './print-filenames.mjs';

const INTERIOR_WIDTH_PT = 414.72;
const INTERIOR_HEIGHT_PT = 630.72;
const INTERIOR_BLEED_PT = 9.36;
const INTERIOR_TRIM_WIDTH_PT = 396;
const INTERIOR_TRIM_HEIGHT_PT = 612;
const FLATTEN_DPI = 300;

const printPaths = printOutputPaths();

function pageCount(path) {
  const info = execFileSync('pdfinfo', [path], {
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  const match = info.match(/^Pages:\s+(\d+)/m);
  if (!match) {
    throw new Error(`could not determine page count for ${path}`);
  }
  return Number(match[1]);
}

function rasterizeInterior(workDir) {
  const rasterPrefix = join(workDir, 'interior-page');
  execFileSync(
    'pdftoppm',
    ['-png', '-r', String(FLATTEN_DPI), printPaths.interior, rasterPrefix],
    { stdio: 'inherit' },
  );
  return rasterPrefix;
}

function rasterizedPagePaths(workDir, expectedPages) {
  const paths = readdirSync(workDir)
    .filter((name) => /^interior-page-\d+\.png$/.test(name))
    .sort((a, b) => a.localeCompare(b, undefined, { numeric: true }))
    .map((name) => join(workDir, name));

  if (paths.length !== expectedPages) {
    throw new Error(
      `expected ${expectedPages} rasterized interior pages, found ${paths.length}`,
    );
  }

  return paths;
}

async function flattenInterior() {
  const pages = pageCount(printPaths.interior);
  const workDir = mkdtempSync(join(tmpdir(), 'fieldnotes-interior-flatten-'));

  try {
    rasterizeInterior(workDir);
    const rasterPaths = rasterizedPagePaths(workDir, pages);
    const pdf = await PDFDocument.create();
    pdf.setTitle("O'ahu A.I. Field Notes Inner Pages Flattened");
    pdf.setAuthor('Kevin Nguyen');
    pdf.setProducer('Oahu AI Field Notes print pipeline');
    pdf.setCreator('Oahu AI Field Notes flatten-interior');

    for (const [index, rasterPath] of rasterPaths.entries()) {
      const pageNumber = index + 1;
      const raster = await pdf.embedPng(readFileSync(rasterPath));
      const page = pdf.addPage([INTERIOR_WIDTH_PT, INTERIOR_HEIGHT_PT]);
      page.setMediaBox(0, 0, INTERIOR_WIDTH_PT, INTERIOR_HEIGHT_PT);
      page.setCropBox(0, 0, INTERIOR_WIDTH_PT, INTERIOR_HEIGHT_PT);
      page.setBleedBox(0, 0, INTERIOR_WIDTH_PT, INTERIOR_HEIGHT_PT);
      page.setTrimBox(
        INTERIOR_BLEED_PT,
        INTERIOR_BLEED_PT,
        INTERIOR_TRIM_WIDTH_PT,
        INTERIOR_TRIM_HEIGHT_PT,
      );
      page.setArtBox(0, 0, INTERIOR_WIDTH_PT, INTERIOR_HEIGHT_PT);
      page.drawImage(raster, {
        x: 0,
        y: 0,
        width: INTERIOR_WIDTH_PT,
        height: INTERIOR_HEIGHT_PT,
      });
      console.log(`flattened interior page ${pageNumber}/${pages}`);
    }

    writeFileSync(printPaths.interiorFlattened, await pdf.save());
    console.log(`flattened interior output: ${printPaths.interiorFlattened}`);
  } finally {
    rmSync(workDir, { recursive: true, force: true });
  }
}

flattenInterior().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
