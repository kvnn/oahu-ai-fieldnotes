// @ts-check
import baseConfig from './vivliostyle.config.js';
import { printOutputPaths } from './scripts/print-filenames.mjs';

const printPaths = printOutputPaths();

export default {
  ...baseConfig,
  size: '11.18in,8.5in',
  theme: './styles/cover.css',
  toc: false,
  entry: [
    {
      path: 'dist/generated-book/cover.html',
      title: 'O‘ahu A.I. Field Notes Cover',
    },
  ],
  output: [
    {
      path: printPaths.coverSource,
      format: 'pdf',
      pdfPostprocess: baseConfig.output[0].pdfPostprocess,
    },
  ],
};
