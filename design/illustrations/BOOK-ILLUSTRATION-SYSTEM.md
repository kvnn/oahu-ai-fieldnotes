# Book Illustration System

This is the reusable illustration contract for the Field Notes book engine. The first
gold-standard set is `design/illustrations/oahu-vol-1.toml` plus the six SVGs in
`assets/figures/ch0*-*.svg`.

## Figure Types

- `opener_motif`: a transparent SVG placed inside the dark chapter opener. It has no
  external caption and should read as a quiet conceptual artifact beside the roman
  numeral/title composition.
- `inline_infographic`: a paragraph-scale SVG placed in the body text at a manifest
  anchor. It should occupy roughly the space of a substantial paragraph, not a full page.
- `dark_plate`: reserved for future full-page figures. Do not use it in this volume
  unless the manifest explicitly asks for it.

## Manifest Contract

Each book owns a TOML manifest with one figure per intended visual slot.

Required fields:

- `id`: stable figure id, also used as `data-illustration-id`.
- `chapter_slug`: slug from the compiled book chapter.
- `asset_path`: SVG path from repo root.
- `treatment`: `opener_motif` or `inline_infographic`.
- `anchor_text`: exact body text for inline placement; blank for opener motifs.
- `fallback_placement`: deterministic fallback if the anchor drifts.
- `caption_policy`: `none` for opener motifs, `internal` for inline infographics.
- `alt_text`: concise description for rendered `<img>` tags.

Generated `dist` files are never edited by hand. Render insertion reads the manifest and
places figures during Vivliostyle markdown compilation.

## Visual Grammar

Use transparent SVG backgrounds. CSS owns page color and dark plates.

Color roles:

| role | hex |
|---|---|
| opener/dark page background | `#19142a` via CSS only |
| structure, frames, rails | `#aba28d` |
| artifact | `#efe6ce` |
| artifact text | `#221733` |
| emphasis, gate, threshold | `#9b7fbc` |
| destination or bright label | `#c8bfa9` |
| meta tie and caption | `#6b5a82` |
| muted labels | `#8b8474` |

The load-bearing rule: `#efe6ce` appears only on the central artifact. Structure is
parchment; the one human-weight moment is aubergine.

## SVG Rules

- Use plain SVG, no scripts, no external assets, no raster screenshots.
- Include `role="img"`, `<title>`, and `<desc>`.
- Use `font-family: 'IBM Plex Mono', monospace` for mono labels.
- Keep captions inside inline infographic SVGs.
- Keep opener motif SVGs captionless and transparent.
- Prefer abstract truthful renderings over decorative symbols. Literal interfaces should
  be redrawn faithfully as simplified systems, not pasted as screenshots.

## Validation

Gold-standard tests should assert:

- manifest assets exist and match chapter slugs;
- all SVGs have accessible title/description metadata;
- no SVG hardcodes the dark page background;
- `#efe6ce` appears exactly once per illustration SVG;
- all illustration colors are present in the CMYK override map;
- compiled Vivliostyle markdown includes exactly the manifest figure count.
