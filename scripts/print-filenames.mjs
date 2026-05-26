import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

export const BOOK_OUTPUT_TITLE = 'Oahu AI Field Notes';
export const BOOK_OUTPUT_FILE_STEM = 'oahu-ai-field-notes';
export const PRINT_BUILD_ID_ENV = 'FIELDNOTES_PRINT_BUILD_ID';
export const UPLOAD_COVER_FILE = `01_${BOOK_OUTPUT_FILE_STEM}_front-back-spine-cover.pdf`;
export const UPLOAD_INTERIOR_FILE = `02_${BOOK_OUTPUT_FILE_STEM}_inner-pages.pdf`;

function pad(value) {
  return String(value).padStart(2, '0');
}

export function shortDatetimeStamp(date = new Date()) {
  const year = date.getFullYear();
  const month = pad(date.getMonth() + 1);
  const day = pad(date.getDate());
  const hour = pad(date.getHours());
  const minute = pad(date.getMinutes());
  const second = pad(date.getSeconds());
  return `${year}${month}${day}-${hour}${minute}${second}`;
}

export function printBuildId(env = process.env) {
  return env[PRINT_BUILD_ID_ENV] || shortDatetimeStamp();
}

export function printOutputPaths(buildId = printBuildId()) {
  return {
    cover: `dist/${UPLOAD_COVER_FILE}`,
    interior: `dist/${UPLOAD_INTERIOR_FILE}`,
  };
}

export function printBuildManifest(buildId = printBuildId()) {
  return {
    bookTitle: BOOK_OUTPUT_TITLE,
    fileStem: BOOK_OUTPUT_FILE_STEM,
    buildId,
    generatedAt: new Date().toISOString(),
    outputPaths: printOutputPaths(buildId),
  };
}

const invokedPath = process.argv[1] ? resolve(process.argv[1]) : '';
if (resolve(fileURLToPath(import.meta.url)) === invokedPath) {
  if (process.argv[2] === 'id') {
    console.log(printBuildId());
  } else {
    console.log(JSON.stringify(printBuildManifest(), null, 2));
  }
}
