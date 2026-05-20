// @ts-check
import baseConfig from './vivliostyle.config.js';

export default {
  ...baseConfig,
  theme: './styles/print-upload.css',
  entry: [
    {
      path: 'dist/generated-book/book.md',
      title: 'Database Book',
    },
  ],
  output: [
    {
      path: 'dist/oahu-ai-field-notes-print.pdf',
      format: 'pdf',
      pdfPostprocess: baseConfig.output[0].pdfPostprocess,
    },
  ],
};
