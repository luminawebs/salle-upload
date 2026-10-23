"""
What the user sees of a run, kept apart from what the code logs.

A run used to print every log line to the web terminal: 20,000+ lines for one
course, almost all diagnostics (Selenium sub-steps, every link on a page). Now
there are two audiences:

- The user (web terminal): one line per step ("[PASO 3/9 F1] Creando
  secciones y actividades"), one line per result ("✓ Rúbrica subida: …"),
  plus every warning and error. Written through the "progreso" logger; see
  console_handler(), which shows only these.
- The developer (file): every line at DEBUG level, one file per run in
  logs/<curso>/run_<fecha>.log (outside workspace/, which a new upload
  wipes). See file_handler(). The web UI downloads it as the full log.

The step marker carries its position and its phase (F0-F3, the terminal's
tabs), so the UI sets the progress bar and the tab from it instead of
guessing from keywords.
"""
import glob
import logging
import os
import sys
import time

from config.settings import Config

LOGGER_NAME = "progreso"
logger = logging.getLogger(LOGGER_NAME)

SUMMARY_PREFIX = "[RESUMEN]"
LOGS_DIR = os.path.join(Config.BASE_DIR, "logs")
KEEP_RUNS = 10  # per course

# (key, title shown to the user, terminal phase: 0 Procesamiento, 1 Estructura,
# 2 Evaluaciones, 3 Finalización), in the order main.py runs them.
STEPS = (
    ("documento", "Leyendo el documento", 0),
    ("formato_inicio", "Preparando el formato del curso", 1),
    ("estructura", "Creando secciones y actividades", 1),
    ("generalidades", "Subiendo la presentación del curso", 1),
    ("glosario", "Importando el glosario", 1),
    ("descripciones", "Subiendo las descripciones de las actividades", 1),
    ("materiales", "Agregando los materiales de estudio", 1),
    ("cuestionarios", "Importando las preguntas de los cuestionarios", 2),
    ("unidades", "Subiendo las introducciones de las unidades", 1),
    ("rubricas", "Subiendo las rúbricas", 2),
    ("finalizacion", "Configurando la finalización de las actividades", 3),
    ("formato_final", "Aplicando el formato final del curso", 3),
)
_TITLES = {key: (title, phase) for key, title, phase in STEPS}

# Libraries that log every HTTP call at DEBUG: kept out of the file too.
_NOISY_LIBRARIES = ("selenium", "urllib3", "httpx", "httpcore", "google_genai", "PIL", "asyncio", "trio", "WDM")

_page_loads = []    # [(seconds, url)] of this course's driver.get() calls
_page_breakdowns = []  # the browser's split of each of them (record_page_load)
_plan = []          # enabled step keys for the current course
_current = None     # (key, start time)
_durations = []     # [(title, seconds)]


def begin_course(enabled_steps: list) -> None:
    """The steps this run will go through, in order (for "Paso 3 de 9")."""
    global _plan, _current, _durations
    _plan = [key for key, _, _ in STEPS if key in enabled_steps]
    _current, _durations = None, []
    _page_loads.clear()
    _page_breakdowns.clear()


def _close_step() -> None:
    global _current
    if _current:
        key, started = _current
        _durations.append((_TITLES[key][0], time.monotonic() - started))
        _current = None


def step(key: str) -> None:
    _close_step()
    global _current
    title, phase = _TITLES[key]
    position = _plan.index(key) + 1 if key in _plan else len(_plan)
    _current = (key, time.monotonic())
    logger.info(f"[PASO {position}/{max(len(_plan), position)} F{phase}] {title}")


def ok(text: str) -> None:
    """One result the user cares about ("✓ Rúbrica subida: Actividad 1")."""
    logger.info(f"✓ {text}")


def info(text: str) -> None:
    logger.info(text)


def warn(text: str) -> None:
    logger.warning(text)


def record_page_load(url: str, seconds: float, breakdown: dict = None) -> None:
    """
    One driver.get() (core/driver_setup._time_page_loads). `breakdown`: the
    browser's own split of it ({servidor, pagina, archivos} seconds, recursos,
    desde_cache, kb), or None when it couldn't be read.
    """
    _page_loads.append((seconds, url))
    if breakdown:
        _page_breakdowns.append(breakdown)
        detail = (f" (servidor {breakdown['servidor']:.1f} s · página {breakdown['pagina']:.1f} s · "
                  f"archivos {breakdown['archivos']:.1f} s; {breakdown['recursos']} archivos, "
                  f"{breakdown['desde_cache']} desde caché, {breakdown['kb']} KB descargados)")
    else:
        detail = ""
    logging.getLogger("tiempos").debug(f"Página cargada en {seconds:.1f} s{detail}: {url}")


def _duration(seconds: float) -> str:
    minutes = seconds / 60
    return f"{minutes:.0f} min" if minutes >= 1 else f"{seconds:.0f} s"


def page_time_split(breakdowns: list):
    """
    "Tiempo de las páginas: 70 % servidor de Moodle · 25 % archivos…" — how
    much a persistent browser cache could save (the files part), or None.
    """
    total = sum(b["servidor"] + b["pagina"] + b["archivos"] for b in breakdowns)
    if not breakdowns or total <= 0:
        return None
    pct = {k: round(100 * sum(b[k] for b in breakdowns) / total) for k in ("servidor", "pagina", "archivos")}
    files = sum(b["recursos"] for b in breakdowns)
    cached = sum(b["desde_cache"] for b in breakdowns)
    mb = sum(b["kb"] for b in breakdowns) / 1024
    return (f"Tiempo de las páginas: {pct['servidor']} % servidor de Moodle · {pct['pagina']} % descarga de la página · "
            f"{pct['archivos']} % archivos y scripts ({files} archivos, {cached} desde caché, {mb:.1f} MB descargados)")


def summary_lines() -> list:
    """Time per step, and page loads, for the end-of-course summary."""
    _close_step()
    lines = [f"{title}: {_duration(seconds)}" for title, seconds in _durations]
    if _page_loads:
        total = sum(s for s, _ in _page_loads)
        lines.append(f"Cargas de página: {len(_page_loads)} · {_duration(total)} en total · "
                     f"{total / len(_page_loads):.0f} s de promedio")
        split = page_time_split(_page_breakdowns)
        if split:
            lines.append(split)
        slowest = sorted(_page_loads, reverse=True)[:5]
        logging.getLogger("tiempos").debug("Páginas más lentas: " + "; ".join(f"{s:.0f} s {u}" for s, u in slowest))
    return lines


# --- Handlers -----------------------------------------------------------------

_LEVEL_LABELS = {logging.WARNING: "Aviso", logging.ERROR: "Error", logging.CRITICAL: "Error"}


class _UserFacing(logging.Filter):
    """The web terminal: progress lines, the end summary, warnings and errors."""

    def filter(self, record):
        return (record.name == LOGGER_NAME or record.levelno >= logging.WARNING
                or SUMMARY_PREFIX in record.getMessage())


class _UserFormatter(logging.Formatter):
    def format(self, record):
        message = record.getMessage()
        if record.name == LOGGER_NAME or SUMMARY_PREFIX in message:
            text = message
        else:
            text = f"{_LEVEL_LABELS.get(record.levelno, 'Info')}: {message}"
        if record.exc_info:
            text += "\n" + self.formatException(record.exc_info)
        return text


def console_handler() -> logging.Handler:
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    handler.addFilter(_UserFacing())
    handler.setFormatter(_UserFormatter())
    return handler


def configure_root() -> None:
    """main.py: everything reaches the handlers at DEBUG; the console shows only the user's part."""
    # The server decodes this process's output as UTF-8; Windows would write
    # accents and "…" in its own code page (they arrived as "�").
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (ValueError, OSError):
            pass
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    for handler in list(root.handlers):
        root.removeHandler(handler)
    root.addHandler(console_handler())
    for name in _NOISY_LIBRARIES:
        logging.getLogger(name).setLevel(logging.WARNING)


def run_log_dir(course_id) -> str:
    return os.path.join(LOGS_DIR, str(course_id))


def file_handler(course_id) -> logging.Handler:
    """Every line of this course's run at DEBUG, in a new file; keeps the last KEEP_RUNS."""
    directory = run_log_dir(course_id)
    os.makedirs(directory, exist_ok=True)
    for old in sorted(glob.glob(os.path.join(directory, "run_*.log")))[:-(KEEP_RUNS - 1) or None]:
        try:
            os.remove(old)
        except OSError:
            pass
    path = os.path.join(directory, time.strftime("run_%Y%m%d_%H%M%S.log"))
    handler = logging.FileHandler(path, mode="w", encoding="utf-8")
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    return handler


def latest_run_log(course_id):
    files = sorted(glob.glob(os.path.join(run_log_dir(course_id), "run_*.log")))
    return files[-1] if files else None
