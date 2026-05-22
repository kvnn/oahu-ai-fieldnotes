// @ts-check
import baseConfig from './vivliostyle.config.js';

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
      path: 'dist/cover.pdf',
      format: 'pdf',
      pdfPostprocess: baseConfig.output[0].pdfPostprocess,
    },
  ],
};
