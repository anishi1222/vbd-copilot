# Japanese Output Authoring Guide

This guide explains how to produce Japanese (`日本語`) presentations with
`pptx_utils.py`. It is referenced from `slide-builder-subagent` when the
slide-conductor passes `OUTPUT_LANGUAGE: ja` for a build.

## Activating Japanese mode

The conductor inserts `set_language('ja')` **before** `create_presentation()`
in the assembled generator script:

```python
from pptx_utils import *
set_theme('light')         # or 'dark'
set_language('ja')         # MUST come before create_presentation()
TOTAL = 24

def build():
    prs = create_presentation()
    # ... fragments ...
```

Once active, every public helper that creates text runs (`add_textbox`,
`add_bullet_list`, `add_styled_table`, `add_metric_card`, the slide-template
functions, etc.) writes both:

- `<a:latin typeface="Segoe UI">` -- the existing Latin face
- `<a:ea typeface="Yu Gothic UI">` -- new East Asian fallback for CJK glyphs

Latin characters continue to render in Segoe UI; only Japanese characters
fall through to Yu Gothic UI. The two faces share the same point size and
weight, producing a clean mixed-language line.

## Font availability

| Platform | Yu Gothic UI | Yu Gothic UI Light | Substitute |
|----------|--------------|--------------------|------------|
| Windows 8.1+ / Office on Windows | shipped | shipped | -- |
| Office for Mac | substituted | substituted | Hiragino Sans (PowerPoint default) |
| LibreOffice (Linux) | n/a | n/a | Noto Sans CJK JP if installed |

The substitution is handled by PowerPoint at render time. Authoring code
does not need to detect the platform.

## Bold and emphasis

`**bold**` markup, `bold=True`, and the existing typography hierarchy work
without changes:

| Latin face | EA face | Notes |
|------------|---------|-------|
| `Segoe UI` | `Yu Gothic UI` | regular body text |
| `Segoe UI Semibold` | `Yu Gothic UI` | bold markup; the run-level `font.bold = True` carries the weight to EA glyphs |
| `Segoe UI Light` | `Yu Gothic UI Light` | lead / section / impact titles |
| `Courier New` | (none) | code blocks keep monospace alignment -- do **not** put Japanese inside `add_code_block()` |

## Authoring rules for Japanese slides

1. **Mixing English product names is fine.** "Azure Container Apps の入門"
   renders cleanly because Latin glyphs stay in Segoe UI and `の入門` falls
   through to Yu Gothic UI.

2. **Keep code blocks in English.** The `add_code_block()` helper sets only
   the Latin typeface so that monospaced alignment is preserved. Comments
   in Japanese will fall back to PowerPoint's default CJK font and may
   look misaligned. Translate the surrounding narrative instead.

3. **Watch line length.** Japanese characters are roughly twice as wide as
   Latin glyphs. A bullet line that fits in English at 24 pt may wrap in
   Japanese -- prefer concise phrasing or drop the font size by 1-2 pt.

4. **Bullet glyphs.** The default `•` bullet character renders in Yu Gothic
   UI under Japanese mode. If you want the more conventional `・` middle
   dot, pass `bullet_char='・'` to `add_bullet_list()`.

5. **Speaker notes are full Japanese transcripts.** They follow the same
   "human voice" rules as the rest of the deck -- avoid robotic
   `〜と言えるでしょう` / `〜について述べます` constructions.

6. **Avoid em-dashes.** PowerPoint renders `―` (U+2015) and `―` line-noise
   inconsistently across CJK fonts. Use `、` or `。` for natural pauses,
   or split into two sentences.

## File naming convention

Slide-conductor appends a `-ja` suffix to the output filename so that the
Japanese build coexists with any English variant:

```
outputs/slides/aks-l300-1h.pptx        # English
outputs/slides/aks-l300-1h-ja.pptx     # 日本語
outputs/slides/aks-l300-1h-dark-ja.pptx
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Japanese chars render in a serif typeface | `set_language('ja')` was called **after** `create_presentation()` | Move the call to the top of the generator |
| Code block alignment broken | Japanese characters placed inside `add_code_block()` | Move the Japanese text out of the code block, into surrounding bullets or a callout |
| Two consecutive bullets look identical width | Long Japanese text auto-wrapped onto two lines | Shorten the bullet or call `add_bullet_list(..., font_size=14)` to drop one step |
| Bold Japanese looks too heavy | `Yu Gothic UI` rendered with `font.bold = True` doubles the weight on some installs | Drop the `**...**` markup for that one phrase; the surrounding emphasis usually still reads as bold |
