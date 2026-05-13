// @ts-check
import { defineConfig } from '@vivliostyle/cli';

export default defineConfig({
  title: 'Oahu AI Field Notes',
  author: 'Kevin Nguyen',
  language: 'en',
  size: '6in,9in',
  theme: './styles/book.css',
  workspaceDir: '.vivliostyle',
  entry: [
    {
      path: 'manuscript/cover.md',
      output: 'cover.html',
      title: 'Cover',
    },
    {
      rel: 'contents',
    },
    {
      path: 'manuscript/00-frontmatter.md',
      title: 'Front Matter',
    },
    {
      path: 'manuscript/01-introduction.md',
      title: 'Introduction',
    },
    {
      path: 'manuscript/02-field-note-template.md',
      title: 'Field Note Template',
    },
  ],
  toc: {
    title: 'Contents',
    sectionDepth: 2,
  },
  copyAsset: {
    includes: ['assets/**/*'],
  },
  output: [
    {
      path: 'dist/oahu-ai-field-notes.pdf',
      format: 'pdf',
    },
    {
      path: 'dist/webpub',
      format: 'webpub',
    },
  ],
});
