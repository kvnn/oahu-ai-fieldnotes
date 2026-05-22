// @ts-check
import baseConfig from './vivliostyle.config.js';

export default {
  ...baseConfig,
  theme: './styles/print-upload.css',
  output: [
    {
      path: 'dist/interior.pdf',
      format: 'pdf',
      pdfPostprocess: baseConfig.output[0].pdfPostprocess,
    },
  ],
};
