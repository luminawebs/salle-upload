# Project Overview — automatizacion_selenium_fase02

> **Purpose for AI agents:** This document is the single source of truth for project structure and module responsibilities. Read it in full before editing any file.

## What This Project Does

A Python + Selenium automation pipeline that connects to a Moodle LMS, scrapes course activity content, transforms it into styled HTML widgets, and re-uploads it back to Moodle. Each type of course content (infographics, forums, news, quizzes, bibliographies) has its own dedicated *action* module.

---

## Directory Layout

```
automatizacion_selenium_fase02/
│
├── main.py                  # Entry point — orchestrates all enabled workflows
├── requirements.txt         # Python dependencies
├── .env                     # Credentials & feature flags (NOT committed to git)
├── .env.example             # Template for .env
│
├── config/
│   └── settings.py          # Central config class; reads from .env
│
├── core/
│   └── driver_setup.py      # Creates & configures the Selenium WebDriver
│
├── actions/                 # One file per Moodle content type
│   ├── moodle_actions.py         # Login, navigation helpers
│   ├── section_actions.py        # Rename / update section descriptions
│   ├── infografia_actions.py     # Orchestrator for infografía workflow
│   ├── infografia_parser.py      # HTML parser + slide builder for infografías
│   ├── foro_actions.py           # Forum content extraction & HTML generation
│   ├── actualidad_actions.py     # "Actualidad" (news) extraction & HTML generation
│   ├── preguntas_actions.py      # Quiz / afianzamiento question processing
│   ├── recursos_apoyo_actions.py # Glossary upload for bibliography entries
│   └── depositphotos_actions.py  # Downloads & resizes Depositphotos images
│
├── assets/
│   ├── templates/           # Shared HTML/image base templates
│   ├── <course_id>/         # One folder per Moodle course ID
│   │   ├── contenidos.json       # Master data file for the course
│   │   ├── infografias/          # Generated infografía HTML outputs
│   │   │   └── raw/              # RAW HTML scraped from Moodle (debug copies)
│   │   ├── actualidad/           # Generated actualidad HTML outputs
│   │   ├── foro/                 # Generated foro HTML outputs
│   │   └── afianzamiento/        # Source HTML for quiz questions
│   └── (shared images / logos)
│
├── html_generator/          # Standalone script to batch-generate HTML from contenidos.json
│   └── generate_html.py
│
└── docs/                    # ← You are here
    ├── README.md
    ├── project_overview.md
    ├── configuration_guide.md
    └── infografia_workflow.md
```

---

## Module Responsibilities

### `main.py`
- Reads `Config.COURSES_TO_PROCESS` and iterates over each course ID.
- Enables Moodle edit mode once per course.
- Calls each workflow function only if its feature flag is `True`.
- All feature flags are checked via `Config.*` — never hardcoded in `main.py`.

### `config/settings.py`
- Single `Config` class with class-level attributes.
- All values come from environment variables via `os.getenv()` with safe defaults.
- `COURSES_TO_PROCESS` is a Python list and is the **only place** to change which courses run.
- See [configuration_guide.md](configuration_guide.md) for full reference.

### `core/driver_setup.py`
- Returns a configured `selenium.webdriver.Chrome` instance.
- Respects `Config.HEADLESS_MODE`.

### `actions/moodle_actions.py`
- `MoodleAutomation` class: `login()`, `navigate_to_course()`.
- All other action modules receive the already-logged-in `driver` object.

### `actions/infografia_actions.py`
- Navigates to the **VIR - INFOGRAFÍA INTERACTIVA** activity for each week.
- Scrapes the raw WYSIWYG HTML and saves a debug copy under `assets/<id>/infografias/raw/RAW_sN_infografia.html`.
- Calls `infografia_parser.parse_infografia_html()` to extract structured slide data.
- Renders the final carousel HTML and saves it to `assets/<id>/infografias/sN_infografia.html`.
- See [infografia_workflow.md](infografia_workflow.md) for deep detail.

### `actions/infografia_parser.py`
- Pure parsing & rendering — **no Selenium, no file I/O**.
- `parse_infografia_html(raw_html)` → `{"slides": [...], "deposit_photos": [...]}`.
- `build_infografia_html(slides, ...)` → final HTML string.
- Key helpers: `split_paragraphs_by_limit()`, `_build_reference_text()`, `_process_text_for_leer_mas()`.

### `actions/foro_actions.py`
- Extracts forum descriptions, indications, hours, resources, professor roles.
- Outputs go to `assets/<id>/foro/sN_foro.html`.

### `actions/actualidad_actions.py`
- Extracts "Actualidad" / news content.
- Outputs go to `assets/<id>/actualidad/sN_actualidad.html`.

### `actions/preguntas_actions.py`
- Reads local HTML files from `assets/<id>/afianzamiento/`.
- Parses True/False questions and splits them between week pairs (S1/S2, S3/S4, …).
- Updates `contenidos.json` and uploads HTML to Moodle via Selenium.

### `actions/recursos_apoyo_actions.py`
- Uploads bibliography / actualidad entries to a Moodle glossary ("Recursos de apoyo").
- Handles category assignment (Unidad 1–3) and auto-linking settings.

### `actions/depositphotos_actions.py`
- Reads Depositphotos URLs collected during infografía parsing.
- Downloads each image and resizes it to **500 px wide** (maintaining aspect ratio).
- Saves to `assets/<id>/infografias/images/`.

---

## Data Flow (High Level)

```
Moodle (live)
    │
    ▼  Selenium scrapes WYSIWYG HTML
RAW_sN_*.html  (debug copy saved locally)
    │
    ▼  infografia_parser / foro_actions / etc. parse & transform
Structured Python dicts  (slides, references, buttons…)
    │
    ▼  HTML builder renders final widget
sN_infografia.html / sN_foro.html / sN_actualidad.html
    │
    ▼  (future / manual step) upload back to Moodle
```

---

## contenidos.json Schema (per course)

```jsonc
{
  "semana_1": {
    "nombre": "Semana 1: Introducción al derecho contractual",
    "activo": true,          // if false, the week is skipped entirely
    "introduccion": "...",   // HTML string
    "criterios": [...],
    "subtemas": [...]
  },
  "semana_2": { ... },
  ...
}
```

> **AI note:** Always check `activo` before processing a week. Inactive weeks must be skipped without writing any output files.

---

## Key Conventions

| Convention | Detail |
|---|---|
| Feature flags | All live in `Config` as booleans; toggled via `.env` |
| Output naming | `sN_<type>.html` where N = week number (1, 3, 5, 7 for odd weeks etc.) |
| RAW debug copies | Always saved **before** parsing so bugs can be reproduced offline |
| No hardcoded course IDs | Only `Config.COURSES_TO_PROCESS` drives the loop |
| Encoding | All file I/O uses `encoding="utf-8"` |
| Logging | Use `logging.getLogger(__name__)` — never bare `print()` in production code |
