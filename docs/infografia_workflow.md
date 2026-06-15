# Infografía Workflow — Deep Dive

> This document covers the complete lifecycle of the `ENABLE_INFOGRAFIA_EXPORT` workflow: from live Moodle scraping through parsing, pagination, and final HTML rendering.

---

## 1. Overview

```
Moodle Activity
"VIR - INFOGRAFÍA INTERACTIVA"
        │
        │  Selenium (infografia_actions.py)
        ▼
RAW_sN_infografia.html    ← debug copy saved locally BEFORE any parsing
        │
        │  parse_infografia_html()  (infografia_parser.py)
        ▼
slides = [
  { type: "info",       title, subtitle, content, buttons, image },
  { type: "pregunta",   title, subtitle, content, options, correct_answer, feedback },
  { type: "referencias", title, content: ["ref1", "ref2", ...] }
]
        │
        │  build_infografia_html()  (infografia_parser.py)
        ▼
sN_infografia.html        ← final Bootstrap carousel widget
```

---

## 2. Files Involved

| File | Role |
|---|---|
| `actions/infografia_actions.py` | Selenium orchestrator — scrapes, saves RAW, calls parser, writes output |
| `actions/infografia_parser.py` | Pure Python parser + HTML builder — no Selenium, no file I/O |
| `assets/<id>/infografias/raw/RAW_sN_infografia.html` | Debug copy of raw Moodle HTML |
| `assets/<id>/infografias/sN_infografia.html` | Final generated carousel HTML |
| `assets/templates/` | Base images used as slide backgrounds (virtual_info_N.png) |

---

## 3. Moodle Source HTML Structure

The raw Moodle WYSIWYG editor produces this pattern for each slide:

```html
<h2>Slide 1: Elementos del contrato y su existencia</h2>
<h2>Formación del contrato en medios físicos y digitales</h2>   ← subtitle
<p>Paragraph of body text...</p>
<p>Botón. Título: Content inside this button...</p>
<p>https://depositphotos.com/photo/...  (image link)</p>

<h2>Pregunta Slide 1</h2>
<h2>Question subtitle text</h2>
<p>Question body text</p>
<p>a) Option A</p>
<p>b) Option B</p>
<p>Respuesta correcta: a)</p>
<p>Retroalimentación: Explanation text here</p>

<p>Referencias:</p>
<ul>
  <li>Author, A. (2021). Title. Publisher. https://doi.org/...</li>
  <li>...</li>
</ul>
```

### Critical parser rules

| Element | Parser action |
|---|---|
| `<h2>` matching `Slide N:` or `Pregunta Slide N:` | Opens a new slide |
| Next `<h2>` after a slide header | Treated as **subtitle** (NOT a new slide) |
| `<h2>` inside a referencias section | Treated as subtitle of current slide |
| `<p>` matching `Referencias:` or `Bibliografía:` | Opens a referencias slide |
| `<p>` with `depositphotos.com` link | Sets `slide["image"]`; text removed from content |
| `<p>` starting with `Botón.` | Appends a new button to `slide["buttons"]` |
| `<p>` after last button with no button prefix | Appends to last button's content |
| `<li>` inside referencias | Reconstructed via `_build_reference_text()` using `<a href>` |

> **Why `<h2>` was added:** The original parser only scanned `<p>` and `<li>`, so slide boundaries (`<h2>` elements) were invisible and **all slide content was silently dropped**. This was fixed — always keep `h2` in the element scan.

---

## 4. Parser Functions (`infografia_parser.py`)

### `parse_infografia_html(raw_html) → dict`

Main entry point.

```python
result = parse_infografia_html(raw_html)
slides          = result["slides"]          # list of slide dicts
deposit_photos  = result["deposit_photos"]  # list of unique Depositphotos URLs
```

**Slide dict keys:**

| Key | Present in types | Description |
|---|---|---|
| `title` | all | Raw `<h2>` trigger text (`"Slide 1: ..."`) |
| `subtitle` | info, pregunta | The second `<h2>` text |
| `type` | all | `"info"` / `"pregunta"` / `"referencias"` |
| `content` | all | List of body paragraph strings |
| `buttons` | info | List of `{"title": str, "content": [str]}` dicts |
| `image` | info | Depositphotos URL string or `None` |
| `options` | pregunta | List of answer option strings (`"a) ..."`) |
| `correct_answer` | pregunta | String like `"a)"` |
| `feedback` | pregunta | Retroalimentación text |

---

### `_build_reference_text(el) → str | None`

Reconstructs a clean reference string from a `<p>` or `<li>` element.

**Problem it solves:** Moodle's editor sometimes wraps long URLs across multiple `<a>` tags with broken visible text. This function uses `el.find("a")["href"]` as the canonical URL instead of the visible anchor text.

**Input:** A BeautifulSoup `Tag` object.  
**Output:** A single cleaned string, or `None` if empty.

---

### `split_paragraphs_by_limit(paragraphs) → (first_batch, overflow_batch)`

Splits a list of reference paragraphs at the point where ANY of these limits is exceeded:

| Metric | Limit |
|---|---|
| Word count | 65 |
| Characters without spaces | 525 |
| Characters with spaces | 600 |

- Returns `(first_batch, [])` if content fits in one slide.
- Returns `(first_batch, overflow_batch)` where no paragraph is duplicated or split mid-sentence.
- Used by the referencias slide builder to create continuation slides automatically.

---

### `_process_text_for_leer_mas(content_paragraphs) → (slide_paragraphs, modal_paragraphs, has_more)`

Splits body content for **info slides** into:
- `slide_paragraphs` — shown directly on the slide (≤ 500 chars total)
- `modal_paragraphs` — shown in a "Leer más" modal
- `has_more` — boolean flag

---

### `build_infografia_html(slides, infografia_base_url, ...) → str`

Assembles the final Bootstrap carousel HTML from the parsed `slides` list.

**Slide type → template mapping:**

| Slide type | Template / background image |
|---|---|
| `info` | `virtual_info_N.png` (cycles 1–4 randomly) |
| `pregunta` | Fixed quiz template |
| `referencias` (first) | `virtual_info_5.png` |
| `referencias` (cont.) | `virtual_info_5.png` — same image, title shows `"Bibliografía (cont.)"` |

---

## 5. Bibliografía Overflow / Pagination

When the references section exceeds the word/character limits, additional carousel slides are generated automatically:

```
Slide: "Bibliografía"          ← virtual_info_5.png, has "Next" button
Slide: "Bibliografía (cont.)"  ← virtual_info_5.png, has "Prev / Home" buttons
Slide: "Bibliografía (cont.)"  ← if needed, repeats
```

**No content is duplicated** — `split_paragraphs_by_limit` guarantees clean boundaries.

---

## 6. Output Files

### RAW debug copy
```
assets/<course_id>/infografias/raw/RAW_sN_infografia.html
```
- Saved **before** parsing.
- Use this file to debug parser issues offline without running Selenium again.
- Contains full Moodle HTML including metadata noise — this is expected.

### Final output
```
assets/<course_id>/infografias/sN_infografia.html
```
- Self-contained Bootstrap carousel widget.
- Ready to paste into Moodle's WYSIWYG editor or serve as a standalone page.

---

## 7. Debugging Checklist

When a week's infografía output is missing content:

1. **Open the RAW file** — `assets/<id>/infografias/raw/RAW_sN_infografia.html`
2. **Check for `<h2>` elements** — each slide must start with an `<h2>`. If Moodle used `<h3>` or `<strong>`, the parser won't detect it.
3. **Count slide blocks** — search for the text `Slide` in the RAW file. The count should match `len(result["slides"])` from the parser.
4. **Check for `docData;DOCY;` strings** — Moodle sometimes embeds metadata in `<p>` tags. These are harmless noise but may affect character counts.
5. **Re-run parse offline:**
   ```python
   from actions.infografia_parser import parse_infografia_html
   with open("assets/4735/infografias/raw/RAW_s1_infografia.html", encoding="utf-8") as f:
       raw = f.read()
   result = parse_infografia_html(raw)
   print(len(result["slides"]), "slides found")
   for s in result["slides"]:
       print(s["type"], "|", s["title"][:60])
   ```

---

## 8. Known Moodle Quirks

| Quirk | Effect | Mitigation |
|---|---|---|
| Double `<h2>` per slide | First = slide trigger, second = subtitle | `_expect_subtitle_h2` flag in parser |
| `<p>` wrapped in `<li>` | Creates duplicate text nodes | Skip `<p>` elements that have a `<li>` parent |
| Split anchor text in references | URL broken across multiple `<a>` tags | `_build_reference_text()` uses `href` not visible text |
| `docData;DOCY;...` metadata in `<p>` | Pollutes content list | Filter: any paragraph starting with `docData` should be skipped (future improvement) |
| Inactive weeks in source | No `<h2>Slide` headers present | Parser returns `[]` — output file not written |

---

## 9. Future Improvements

- [ ] **Strip `docData` metadata** — add a pre-processing pass in `parse_infografia_html` to remove `<p>` elements whose text starts with `docData;`.
- [ ] **Merge `split_paragraphs_by_limit` and `_process_text_for_leer_mas`** into a single `ContentPaginationManager` class.
- [ ] **Auto-detect `<h3>` slide headers** — some Moodle themes render headings as `<h3>` instead of `<h2>`.
- [ ] **Validate image URLs** — check that each Depositphotos URL is reachable before embedding in output.
