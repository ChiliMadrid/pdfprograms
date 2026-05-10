# CM Strength Dynasty Korean HTML-to-PDF Source

This project recreates `CM Strength Dynasty.pdf` as a print-ready static HTML source. The original PDF remains the visual authority. The DOCX is used as the raw text source, and the existing translated Korean DOCX in `../../korean_exports/final/` is used for visible overlay text when present.

## Files

- `index.html` - generated fixed-layout HTML, one section per PDF page.
- `styles.css` - print CSS, letter page sizing, Korean-compatible font stack.
- `assets/pages/` - textless page art extracted from the original PDF.
- `assets/manifest.json` - generation metadata.
- `export-pdf.js` - Playwright PDF export script.

## Install

```powershell
npm install
```

## Regenerate HTML and Page Assets

```powershell
npm run generate
```

## Preview

```powershell
npm run preview
```

Then open:

```text
http://127.0.0.1:4173
```

## Export PDF

```powershell
npm run export
```

The PDF is written to:

```text
output.pdf
```

## Verify

```powershell
npm run verify
```

## Final Production Check

```powershell
npm run final-check
```

This regenerates the HTML/page assets, exports `output.pdf`, runs the structural verifier, and then runs production QA with:

- page/background/patch coverage checks
- full page-by-page missing-content audit
- accidental English phrase detection
- suspicious mixed Korean/English term detection
- tiny font and overflow-risk checks
- duplicate near-overlap checks
- exercise title underline alignment checks
- preview PNG generation

The production QA JSON report is written to:

```text
qa-production-report.json
```

The missing-content audit writes:

```text
qa-reports/missing-content.json
qa-reports/missing-content.md
```

The visual fidelity audit writes:

```text
qa-reports/visual-fidelity.json
qa-reports/visual-fidelity.md
```

Preview PNGs are written to `qa-previews/` for pages:

```text
6, 8, 14, 15, 22, 29, 37, 44, 58, 61, 72, 86, 91
```

`qa-previews/` is ignored because the images are generated review artifacts.

The audit also renders every exported page to:

```text
qa-previews/all-pages/
```

Open this contact sheet for a fast human scan:

```text
qa-previews/contact-sheet.html
```

Rendered original/generated visual comparisons are written to:

```text
qa-previews/visual-diff/
qa-previews/publisher-review/
```

## Publisher Review / Prepress QA

Passing automated QA does not equal publisher approval. Before delivery, run:

```powershell
npm run final-check
```

Then review:

- `qa-reports/visual-fidelity.md` for the highest-difference pages.
- `qa-previews/visual-diff/contact-sheet.html` for all rendered side-by-side page comparisons.
- `qa-previews/publisher-review/index.html` for the curated prepress review set.
- `qa-reports/missing-content.md` for any page with a nonzero missing-content score.

Human review should inspect:

- black/gold header bar size, position, and title alignment
- weekly overview table proportions and row spacing
- exercise title placement and gold underline attachment
- Korean body text density and vertical rhythm
- footer/header relationships
- any page where art patches look visibly different from the original design

Pages still requiring manual visual approval are the pages ranked in `qa-reports/visual-fidelity.md`, especially the current worst visual-difference pages. The visual audit intentionally ranks differences but does not fail automatically yet, because Korean text replacement will always produce some image-level difference from the English original.

After regenerating or editing the overlay, verify:

- `npm run generate` completes without errors.
- `index.html` contains 93 `.pdf-page` sections.
- `assets/pages/` contains 93 `page-*-background.png` files.
- `assets/manifest.json` reports `page_count: 93` and `korean_docx_found: true`.
- `npm run export` writes `output.pdf`.
- `npm run verify` passes.
- `npm run qa` reports zero errors.
- `output.pdf` opens, has 93 letter-sized pages, and visually preserves the original backgrounds, branding, headers, footers, tables, and page scale.
- Spot-check pages 2-5 and workout pages such as 8, 61, 86, and 91 for localized black header bars, readable weekly tables, and no obvious English program text.
- Spot-check the QA preview workout pages for exercise title underline alignment. Gold rules should sit directly under the matching exercise title rather than floating in body copy.
- Review `qa-reports/missing-content.md` for any pages with nonzero audit scores, then scan `qa-previews/contact-sheet.html` before delivery.
- A text extraction scan should leave only intentional brand/acronym text such as CM Strength, Dynasty, RPE, and units.

## English Allowlist

The QA script allows these intentional English terms when scanning the exported PDF text layer:

- CM Strength
- Dynasty
- RPE
- PPL
- URL
- reps
- sets
- kg
- lb / lbs
- percentages and URL/domain text

## Translation Replacement Notes

The visible placeholder spans use the required Korean font stack:

```css
"Noto Sans KR", "Pretendard", "Apple SD Gothic Neo", Arial, sans-serif
```

Each text span includes a `data-source` attribute containing the corresponding DOCX source text where available. Replace or refine the visible Korean text inside `index.html` while keeping the existing positioning styles intact.

## Known Placeholders

Exact original fonts were not embedded as editable web fonts. The HTML uses the required Korean-compatible font stack for all overlay text. The original non-text artwork, borders, tables, image placement, colors, headers, footers, and branding art are preserved as extracted page backgrounds.

Some tables, section bars, workout headers, and exercise title underlines are flattened artwork in the original PDF rather than extractable live text. The generator hides the original workout-page gold rules in the exercise area and redraws title-anchored Korean-layout rules so the underline follows the translated exercise title. These patches are intentionally page-specific and should be adjusted in `tools/generate_project.py` rather than by editing generated `index.html` directly.

PDF text extraction can undercount Korean words because generated overlay text often has tight positioning and reduced spacing. The missing-content audit therefore combines output text extraction with generated overlay coverage, source text counts, exercise/table/set label signals, and human preview artifacts rather than relying on raw output word count alone.
