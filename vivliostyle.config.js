// @ts-check
import { defineConfig } from '@vivliostyle/cli';

export default defineConfig({
  title: 'O‘ahu A.I.',
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
    title: 'FIELD NOTES | VOLUME 01',
    sectionDepth: 2,
  },
  copyAsset: {
    includes: ['assets/fonts/**/*', 'assets/figures/**/*', 'assets/images/**/*', 'assets/curated/**/*'],
  },
  output: [
    {
      path: 'dist/oahu-ai-field-notes.pdf',
      format: 'pdf',
      pdfPostprocess: {
        cmyk: {
          overrideMap: [
            ['#f1e9d4', { c: 500, m: 800, y: 1800, k: 0 }],
            ['#6b4488', { c: 4800, m: 6500, y: 0, k: 4700 }],
            ['#19142a', { c: 4000, m: 5200, y: 0, k: 8400 }],
            ['#2a2520', { c: 0, m: 1200, y: 2400, k: 8400 }],
            ['#8b8474', { c: 0, m: 500, y: 1700, k: 4500 }],
            ['#463f33', { c: 0, m: 1000, y: 2700, k: 7300 }],
            ['#7a7160', { c: 0, m: 700, y: 2100, k: 5200 }],
            ['#b8af9a', { c: 0, m: 500, y: 1600, k: 2800 }],
            ['#e8dfc4', { c: 0, m: 400, y: 1600, k: 900 }],
            ['#9a9a9a', { c: 0, m: 0, y: 0, k: 4000 }],
            ['#eeeeee', { c: 0, m: 0, y: 0, k: 700 }],
          ],
          warnUnmapped: true,
          mapOutput: 'dist/cmyk-map.json',
        },
      },
    },
    {
      path: 'dist/webpub',
      format: 'webpub',
    },
  ],
});
