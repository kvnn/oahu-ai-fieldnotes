import { readFileSync, writeFileSync } from 'node:fs';

import { PDFDocument } from 'pdf-lib';

import { printOutputPaths } from './print-filenames.mjs';

const printPaths = printOutputPaths();

function useTrimBoxForDownload(page) {
  const trimBox = page.getTrimBox();
  page.setMediaBox(trimBox.x, trimBox.y, trimBox.width, trimBox.height);
  page.setCropBox(trimBox.x, trimBox.y, trimBox.width, trimBox.height);
  page.setBleedBox(trimBox.x, trimBox.y, trimBox.width, trimBox.height);
  page.setArtBox(trimBox.x, trimBox.y, trimBox.width, trimBox.height);
}

async function appendPdfPages(target, sourcePath) {
  const source = await PDFDocument.load(readFileSync(sourcePath));
  const copiedPages = await target.copyPages(source, source.getPageIndices());
  for (const page of copiedPages) {
    useTrimBoxForDownload(page);
    target.addPage(page);
  }
  return copiedPages.length;
}

async function buildDownloadPdf() {
  const pdf = await PDFDocument.create();
  pdf.setTitle("O'ahu A.I. Field Notes | Volume 01");
  pdf.setAuthor('Kevin Riggen');
  pdf.setProducer('Oahu AI Field Notes print pipeline');
  pdf.setCreator('Oahu AI Field Notes build-download-pdf');

  const frontCoverPages = await appendPdfPages(pdf, printPaths.coverFront);
  const interiorPages = await appendPdfPages(pdf, printPaths.interior);
  const backCoverPages = await appendPdfPages(pdf, printPaths.coverBack);

  writeFileSync(printPaths.download, await pdf.save());
  console.log(
    [
      `final download output: ${printPaths.download}`,
      `front cover pages: ${frontCoverPages}`,
      `interior pages: ${interiorPages}`,
      `back cover pages: ${backCoverPages}`,
    ].join(' '),
  );
}

buildDownloadPdf().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
