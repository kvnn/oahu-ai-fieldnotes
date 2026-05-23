// @ts-check
import baseConfig from './vivliostyle.config.js';
import { printOutputPaths } from './scripts/print-filenames.mjs';

const printPaths = printOutputPaths();

export default {
  ...baseConfig,
  theme: './styles/print-upload.css',
  output: [
    {
      path: printPaths.interior,
      format: 'pdf',
      pdfPostprocess: baseConfig.output[0].pdfPostprocess,
    },
  ],
};
