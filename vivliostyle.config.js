// @ts-check
import { defineConfig } from '@vivliostyle/cli';

export default defineConfig({
  title: 'Oahu AI Field Notes',
  author: 'Kevin Nguyen',
  language: 'en',
  size: '5.5in,8.5in',
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
    {
      path: 'manuscript/03-ai-workbenches.md',
      title: 'A.I. Workbenches',
    },
    {
      path: 'manuscript/04-hydrate-review-tighten-loop.md',
      title: 'Hydrate / Review / Tighten Loop',
    },
    {
      path: 'manuscript/05-agents-are-the-best-admin-interface.md',
      title: 'Agents Are the Best Admin Interface',
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
