# Oahu AI Field Notes

Book-printing workspace powered by Vivliostyle.

## TO-DO upon Book-Complete
1. add / fix the "Fig 5.1" type annotations to each of the illustrations
2. check for missing citation callouts (e.g. `[1]`)
3. check for missing / broken citation sources (e.g. `1: https://oahu.ai`)
4. generate QR codes for citations

## Requirements

- Node.js 20 or newer
- npm

The project uses a local `@vivliostyle/cli` dev dependency so builds are reproducible from npm scripts. If you also want a global `vivliostyle` command, install it with:

```sh
npm install -g @vivliostyle/cli
```

## Install

```sh
npm install
```

## Preview

```sh
npm run preview
```

## Build

```sh
npm run build
```

Outputs are configured in `vivliostyle.config.js`:

- `dist/oahu-ai-field-notes.pdf`
- `dist/webpub`

Production profiles are available through the Python CLI. The proof profile uses `vivliostyle.proof.config.js` so it keeps the same CMYK postprocess map as the main build.

```sh
fieldnotes render --profile draft
fieldnotes render --profile proof
fieldnotes render --profile print
```

The print profile uses the database-generated manuscript at `dist/generated-book/book.md` and `vivliostyle.database-print.config.js` to produce `dist/interior.pdf` as the Mixam interior upload. The cover is built separately with `vivliostyle.cover.config.js` as `dist/cover.pdf`, a full wrap sized to the local Mixam template: 11.18" x 8.5" trim with a 0.18" spine and 0.13" bleed. The older filesystem manuscript path is available only as `npm run build:print:manuscript`. Confirm both uploads with Mixam's file checker and order one hard proof before a full run.

```sh
npm run build:print
npm run verify:print
```

`verify:print` is intentionally strict: it checks the full-wrap cover size, Cormorant display-font embedding, PDF/X-4 markers, and the priced 68-page interior count.

## Production Design

The custom theme in `styles/book.css` is built for 5.5" x 8.5" print with `0.13in` bleed, crop marks, a `0.875in` outside marginalia rail, `0.625in` inside gutter, `0.5in` top margin, and `0.75in` bottom margin.

The palette is intentionally narrow: warm stock preview, one aubergine accent, rich black dark spreads, and K-100 body type. Local font files should be placed in `assets/fonts` before proof/print output:

- `CormorantGaramond-Regular.ttf`
- `CormorantGaramond-SemiBold.ttf`
- `SourceSerif4-Regular.woff2`
- `SourceSerif4-Semibold.woff2`
- `IBMPlexMono-Regular.woff2`

Initial diagram assets live in `assets/figures` and follow the book grammar: 12-column grid, near-black lines, aubergine state/emphasis, mono caps labels, no decorative fills, and one open-triangle arrowhead.

The first reusable illustration system lives in `design/illustrations/BOOK-ILLUSTRATION-SYSTEM.md`.
The current volume's gold-standard manifest is `design/illustrations/oahu-vol-1.toml`, which
drives chapter-opener motifs and inline SVG infographics during print markdown generation.
Raster and static image placements live outside the SVG illustration system. The current
volume media manifest is `design/media/oahu-vol-1.toml`.

## Manuscript Structure

- `manuscript/cover.md` is the book cover.
- `manuscript/00-frontmatter.md` is the front matter.
- `manuscript/01-introduction.md` starts the main text.
- `manuscript/02-field-note-template.md` is a reusable chapter pattern.
- `styles/book.css` controls page size, margins, typography, figures, tables, and print behavior.
- `assets/images` is for referenced images.

Add new chapters to the `entry` array in `vivliostyle.config.js`.

## Book Media Assets

Use `assets/images/screenshots` for final screenshots that should appear in the printed book. Keep `inbox/screenshots` for raw source ingestion and OCR evidence.

For database-generated chapters, place a screenshot in `assets/images/screenshots` and insert a figure block in the chapter draft:

```html
<figure class="book-media book-screenshot">
  <img src="../../assets/images/screenshots/chapter-slug-short-name.png" alt="Short factual description.">
  <figcaption>Short artifact caption.</figcaption>
</figure>
```

Crop or redact the image before adding it as a final asset. For body-width print, target at least 1200px wide.

For generated title pages, add raster/static opener images to `design/media/oahu-vol-1.toml`
instead of `design/illustrations/oahu-vol-1.toml`. The illustration manifest remains reserved
for generated SVG figures and the illustration workbench.

## Knowledge Database

The Python package in `src/fieldnotes` defines a SQLAlchemy 2.x schema for the knowledge-to-book pipeline:

```text
source material -> knowledge nodes -> field note candidates -> chapter briefs
-> chapter drafts -> evaluations -> Vivliostyle rendered outputs
```

Core tables include projects, source material, source chunks, staged extracted candidates, knowledge nodes, source evidence links, knowledge edges, field note candidates, chapter briefs, chapter drafts, visual assets, book volumes, rendered outputs, evaluations, agent runs, review decisions, tags, and taggings.

Install the Python dependencies:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

Set a database URL when using Postgres. `DB_ENGINE_URL` is supported for compatibility with existing local environment files; `FIELDNOTES_DATABASE_URL` and `DATABASE_URL` are also recognized.

```sh
export DB_ENGINE_URL="postgresql+psycopg://user:password@localhost:5432/fieldnotes"
pip install -e ".[postgres]"
alembic upgrade head
```

If you want raw Postgres DDL instead of Alembic applying the migrations directly, use:

```sh
psql "$POSTGRES_URL" -f schema/postgres_schema.sql
```

The `.env` value is a SQLAlchemy URL, so `alembic upgrade head` is the safer apply path for this project.

## Source-To-Chapter Workflow

`fieldnotes.config.toml` defines the project slug, Vivliostyle config path, model defaults, chunk size, and watch roots. The default inboxes are:

- `inbox/notebooks` for photos of notebook pages
- `inbox/screenshots` for screenshots
- `inbox/transcripts` for meeting transcripts
- `inbox/docs` for uploaded documents
- selected repo summary files from this project and configured read-only context projects

Read-only context roots currently include:

- `/Users/kvnn/Projects/crawlbuild`
- `/Users/kvnn/Projects/LitScenes`
- `/Users/kvnn/Life360/marck-studio`
- `/Users/kvnn/Projects/oahu-ai-builder`
- `/Users/kvnn/Projects/oahuai-seed`

For `repo_summary` roots, ingestion reads only approved top-level summary files such as `README.md`, `AGENTS.md`, `pyproject.toml`, `package.json`, and `vivliostyle.config.js`.

Create tables and seed the initial project:

```sh
fieldnotes init-db
fieldnotes seed
```

Ingest source files. Use `--skip-ocr` when you want image sources recorded as `needs_ocr` without calling OpenAI:

```sh
fieldnotes ingest --skip-ocr
fieldnotes ingest
```

Extract staged candidates. `local` is deterministic and useful for tests or dry runs; the configured default is OpenAI structured extraction:

```sh
fieldnotes extract --provider local
fieldnotes extract
```

Review extracted candidates before they become canonical knowledge nodes:

```sh
fieldnotes serve --port 8765
fieldnotes review promote <candidate-id> --chapter-brief-id <chapter-brief-id>
fieldnotes review reject <candidate-id>
```

Save a newly articulated chapter candidate directly from an agent session:

```sh
fieldnotes chapter save-candidate \
  --title "Seeing for the Blind" \
  --subtitle "Live A.I. vision, signs, menus, rooms, streets, and the return of everyday context" \
  --description "LLM vision can read immediate surroundings fast enough to restore everyday context."
```

The first chapter concept is approved:

```sh
fieldnotes chapter approve book-that-remembers-its-sources \
  --rationale "Approved as the opening chapter concept."
```

Render through Vivliostyle and record the output:

```sh
fieldnotes render
```

Run tests:

```sh
pytest
```

The initial seed creates `O‘ahu A.I. Field Notes Vol. 1`, one volume, example source records, accepted knowledge nodes, an accepted candidate field note cluster, and the approved first chapter brief connected to the Vivliostyle output path.
