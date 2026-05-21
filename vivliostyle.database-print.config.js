// @ts-check
import baseConfig from './vivliostyle.config.js';

const flattenDocumentToc = (nodeList) => (propsList) => ({
  type: 'element',
  tagName: 'ol',
  properties: {},
  children: nodeList.flatMap((doc, index) => {
    const renderedChildren = propsList[index]?.children ?? [];
    const sectionItems = renderedChildren.flatMap((child) => {
      if (child?.type === 'element' && child.tagName === 'ol') {
        return child.children ?? [];
      }
      return child ? [child] : [];
    });

    if (sectionItems.length > 0) {
      return sectionItems;
    }

    return [
      {
        type: 'element',
        tagName: 'li',
        properties: {},
        children: [
          {
            type: 'element',
            tagName: 'a',
            properties: { href: doc.href },
            children: [{ type: 'text', value: doc.title }],
          },
        ],
      },
    ];
  }),
});

export default {
  ...baseConfig,
  theme: './styles/print-upload.css',
  toc: {
    ...baseConfig.toc,
    transformDocumentList: flattenDocumentToc,
  },
  entry: [
    {
      path: 'dist/generated-book/book.md',
      title: baseConfig.title,
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
