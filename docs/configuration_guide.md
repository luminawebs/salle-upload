# Configuration Guide

> All configuration lives in two places: **`.env`** (secrets & runtime overrides) and **`config/settings.py`** (defaults, feature flags, and non-secret settings).

---

## 1. Environment Variables (`.env`)

Copy `.env.example` and fill in your values:

```bash
cp .env.example .env
```

### Full `.env` reference

```dotenv
# ── Moodle credentials ──────────────────────────────────────────────────────
MOODLE_URL=https://your-moodle.example.com
MOODLE_USERNAME=your_username
MOODLE_PASSWORD=your_password

# ── Browser ─────────────────────────────────────────────────────────────────
# Set to True to run Chrome without a visible window
HEADLESS_MODE=False

# ── Feature flags (True / False) ────────────────────────────────────────────
# FASE 01
ENABLE_SECTION_RENAME=False
ENABLE_SECTION_DESCRIPTION_UPDATE=False

# FASE 02
ENABLE_INFOGRAFIA_EXPORT=True
ENABLE_DEPOSITPHOTOS_DOWNLOAD=False
ENABLE_FORO_EXPORT=False
ENABLE_ACTUALIDAD_EXPORT=False
ENABLE_PREGUNTAS_EXPORT=False
ENABLE_RECURSOS_APOYO_EXPORT=False

# ── Depositphotos credentials ────────────────────────────────────────────────
DEPOSITPHOTOS_USER=your@email.com
DEPOSITPHOTOS_PASS=yourpassword
```

> **Security:** `.env` is listed in `.gitignore`. Never commit it. Use `.env.example` as the template.

---

## 2. `config/settings.py` — Config Class Reference

```python
from config.settings import Config
```

### 2.1 Moodle connection

| Attribute | Env var | Default | Notes |
|---|---|---|---|
| `Config.MOODLE_URL` | `MOODLE_URL` | `https://moodle.example.com` | Trailing slash stripped automatically |
| `Config.MOODLE_USERNAME` | `MOODLE_USERNAME` | `None` | Required — script aborts if missing |
| `Config.MOODLE_PASSWORD` | `MOODLE_PASSWORD` | `None` | Required — script aborts if missing |
| `Config.HEADLESS_MODE` | `HEADLESS_MODE` | `False` | `"True"/"1"/"t"` → `True` |
| `Config.EXPLICIT_WAIT_TIME` | *(hardcoded)* | `10` (seconds) | WebDriver explicit wait timeout |

### 2.2 Feature flags

Each flag is read from its env var; if not set, falls back to the default shown.

| Flag | Env var | Default | What it runs |
|---|---|---|---|
| `ENABLE_SECTION_RENAME` | same | `False` | Renames course section titles in Moodle |
| `ENABLE_SECTION_DESCRIPTION_UPDATE` | same | `False` | Updates section description from `contenidos.json` |
| `ENABLE_INFOGRAFIA_EXPORT` | same | `True` | Full infografía scrape → parse → HTML write |
| `ENABLE_DEPOSITPHOTOS_DOWNLOAD` | same | `False` | Downloads & resizes images from Depositphotos |
| `ENABLE_FORO_EXPORT` | same | `False` | Scrapes forum activities → `sN_foro.html` |
| `ENABLE_ACTUALIDAD_EXPORT` | same | `False` | Scrapes actualidad activities → `sN_actualidad.html` |
| `ENABLE_PREGUNTAS_EXPORT` | same | `False` | Reads local afianzamiento HTML → uploads quiz |
| `ENABLE_RECURSOS_APOYO_EXPORT` | same | `False` | Uploads bibliography to Moodle glossary |

> **Tip:** To run only one workflow, set its flag to `True` and leave all others `False`.

### 2.3 Courses to process

```python
# config/settings.py  (line 73–74)
COURSES_TO_PROCESS = [4735]
```

- **Type:** `list[int]` — Moodle course IDs.
- To process multiple courses in one run: `COURSES_TO_PROCESS = [4735, 4737, 4742]`
- The main loop iterates over this list in order.
- Each course must have a matching folder: `assets/<course_id>/`

---

## 3. Adding a New Course

1. Create the folder structure:
   ```
   assets/<new_course_id>/
   ├── contenidos.json        ← copy & fill from an existing course
   ├── infografias/
   │   └── raw/
   ├── actualidad/
   ├── foro/
   └── afianzamiento/
   ```
2. Add the course ID to `Config.COURSES_TO_PROCESS` in `settings.py`.
3. Populate `contenidos.json` with the week data (see schema in `project_overview.md`).

---

## 4. Disabling a Single Week

In `contenidos.json`, set `"activo": false` for the week:

```jsonc
"semana_3": {
  "nombre": "Semana 3: ...",
  "activo": false,   // ← this week will be skipped
  ...
}
```

All action modules check this flag and skip the week without writing output files.

---

## 5. Infografía Image Base URL

When `ENABLE_INFOGRAFIA_EXPORT=True`, the script prompts at startup:

```
Please provide the base URL for infografia images (e.g., https://...s3.amazonaws.com/.../):
```

This is the S3 (or CDN) prefix where Depositphotos images have been uploaded. The parser appends the local filename to this URL when embedding images in the final HTML.

---

## 6. Common Mistakes

| Problem | Fix |
|---|---|
| Script aborts immediately | Check `MOODLE_USERNAME` and `MOODLE_PASSWORD` are set in `.env` |
| Feature runs but no output file appears | Check `activo: true` in `contenidos.json` for the week |
| Images show as broken in output HTML | Verify the S3 base URL ends with `/` and the image was downloaded |
| Multiple infografías missing slides | The RAW file may be malformed — open `assets/<id>/infografias/raw/RAW_sN_infografia.html` and inspect |
| `courses_to_process` has no effect | Make sure you're editing `Config.COURSES_TO_PROCESS` in `settings.py`, not a local variable in `main.py` |
