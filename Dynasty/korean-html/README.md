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

After regenerating or editing the overlay, verify:

- `npm run generate` completes without errors.
- `index.html` contains 93 `.pdf-page` sections.
- `assets/pages/` contains 93 `page-*-background.png` files.
- `assets/manifest.json` reports `page_count: 93` and `korean_docx_found: true`.
- `npm run export` writes `output.pdf`.
- `npm run verify` passes.
- `output.pdf` opens, has 93 letter-sized pages, and visually preserves the original backgrounds, branding, headers, footers, tables, and page scale.

## Translation Replacement Notes

The visible placeholder spans use the required Korean font stack:

```css
"Noto Sans KR", "Pretendard", "Apple SD Gothic Neo", Arial, sans-serif
```

Each text span includes a `data-source` attribute containing the corresponding DOCX source text where available. Replace or refine the visible Korean text inside `index.html` while keeping the existing positioning styles intact.

## Known Placeholders

Exact original fonts were not embedded as editable web fonts. The HTML uses the required Korean-compatible font stack for all overlay text. The original non-text artwork, borders, tables, image placement, colors, headers, footers, and branding art are preserved as extracted page backgrounds.

Some tables and cover typography are flattened artwork in the original PDF rather than extractable live text. Those remain preserved visually in the page backgrounds and should be replaced with localized table artwork if fully editable Korean table text is required.
