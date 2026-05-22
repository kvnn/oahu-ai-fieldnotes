import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';

const outputPath = join('dist', 'generated-book', 'cover.html');

const html = `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>O'ahu A.I. Field Notes Cover</title>
  </head>
  <body>
    <main class="cover-wrap" aria-label="O'ahu A.I. Field Notes cover wrap">
      <section class="cover-panel cover-back" aria-label="Back cover">
        <p class="cover-back-mark">O'AHU A.I. FIELD NOTES</p>
        <p class="cover-back-symbol">&oplus;</p>
      </section>
      <section class="cover-spine" aria-label="Spine"></section>
      <section class="cover-panel cover-front" aria-label="Front cover">
        <header class="cover-topline">
          <span>O'AHU A.I.</span>
          <span>VOL. 01</span>
        </header>
        <div class="cover-rule"></div>
        <div class="cover-title-block">
          <h1>Field<br>Notes</h1>
          <div class="cover-accent-rule"></div>
          <p class="cover-years">2023 - 2026</p>
          <p class="cover-tagline">Notes from the island<br>that builds itself.</p>
        </div>
        <footer class="cover-footer">
          <span>EDITION / 200</span>
          <span>&oplus;</span>
        </footer>
      </section>
    </main>
  </body>
</html>
`;

mkdirSync(dirname(outputPath), { recursive: true });
writeFileSync(outputPath, html, 'utf8');
