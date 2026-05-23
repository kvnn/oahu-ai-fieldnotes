# Workbench Figures — Hand-off to Build Agent
Chapter V (Workbenches), *O'ahu A.I. Field Notes Vol. 1*

## What's in this hand-off

Two illustrations as exact SVG, both designed as full-page dark plates (siblings to the chapter-opener plates):

- `fig-5-1-scatter-condenses.svg` — **locked, rendered, approved.**
- `fig-5-2-what-a-workbench-holds.svg` — **specced, NOT yet visually verified** (render timed out before sign-off). Render it first, then check the two open questions at the bottom before treating it as final.

Not included: the cockpit/session figure and the depth-stack figure. Hold both. Chapter figure count is being decided separately; default rule is **max two figures per chapter**, and these two (wide shot + cutaway) are the current keepers.

## Placement in the chapter markdown

The two figures are a wide-shot → cutaway pair. Keep them in order, ideally within ~2pp of each other — but do NOT force blank pages to achieve adjacency (honors the existing no-waste pagination rule).

- **Fig 5.1** goes immediately AFTER the paragraph ending: *"…and building that home is what a workbench is."*
- **Fig 5.2** goes immediately AFTER the paragraph that enumerates what a workbench holds, ending: *"…never reconstructing context they once had and lost."*

## These are full-page dark plates — print treatment

Each figure occupies a full recto dark plate, sibling to the chapter openers.

1. **One source of truth for the plate color.** The SVGs currently carry their own plate background as the first child: `<rect x="0" y="0" width="…" height="…" fill="#221733"/>`. For print, DELETE that rect from each SVG and set the *page* background to the chapter-opener token instead. `#221733` is a stand-in — the opener background token is canonical. If openers resolve to `#19142A`, the plates must be `#19142A`.
2. **Center the SVG vertically** on the plate; the illustration's own internal margins provide the breathing room. Place it at the **text-block width** (same horizontal measure as body pages), not full bleed.
3. The mono **caption and chapter tie are inside the SVG** — do not add a separate caption element.

## Color grammar — lock these as tokens (every future figure reuses them)

| role | hex | rule |
|---|---|---|
| plate background | = opener token (replaces `#221733`) | canonical; never hardcode |
| structure (lines, frames, zones) | `#ABA28D` | parchment |
| **ARTIFACT** | `#EFE6CE` | cream — **only ever the artifact** |
| artifact label (on cream) | `#221733` | dark text on cream |
| emphasis / gate / threshold | `#9B7FBC` | the one aubergine moment per figure |
| destination / bright label | `#C8BFA9` | |
| meta tie + caption | `#6B5A82` | |
| fig number + zone labels (muted) | `#8B8474` | |

**Load-bearing rule:** cream (`#EFE6CE`) appears ONLY on the artifact, in every figure, no exceptions. Structure is parchment; the single moment of human weight is aubergine. The moment cream touches a non-artifact element, the whole system goes mute.

## Two substitutions the agent MUST make for print

1. **Mono font.** SVG labels are set to `'IBM Plex Mono','SF Mono','Menlo',monospace`. Make `IBM Plex Mono` (or whatever the book's embedded mono actually is) the real embedded family so labels embed in the PDF instead of substituting on the RIP. Verify with `pdffonts` → emb: yes.
2. **CMYK.** Add the seven hexes above to the CMYK override map and run them through the same pipeline as the rest of the book. Confirm `#9B7FBC` (aubergine) and `#EFE6CE` (cream) on the **hard proof** against 100lb Satin Text before final — both shift on coated satin.

## Open questions for 5.2 — check after first render

- **STATE strip** is six small outlined cells. If it reads as a UI widget rather than abstract status, drop to three cells, or swap cells for plain ticks. (Constraint was "no UI hints.")
- **Three faint service arrows** (material→artifact, tools→artifact, artifact→gate) are meant to say *serves*, not *then*. If they read as a pipeline/flow instead of composition, cut all three and let cream dominance + spatial arrangement carry it.

## Accessibility

Each SVG carries `role="img"` + `<title>` + `<desc>`. Preserve them verbatim.

## Suggested test additions

- Assert each figure SVG is present and references the opener background token (not a hardcoded `#221733`).
- Assert `#EFE6CE` appears exactly once per figure (artifact only) — a cheap regression guard for the grammar rule.
- `pdffonts` shows the mono family embedded, not substituted.
