// @ts-check
import baseConfig from './vivliostyle.config.js';

export default {
  ...baseConfig,
  output: [
    {
      path: 'dist/oahu-ai-field-notes-proof.pdf',
      format: 'pdf',
      pdfPostprocess: baseConfig.output[0].pdfPostprocess,
    },
  ],
};
