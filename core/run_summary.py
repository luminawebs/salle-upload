"""
Honest end-of-run reporting for main.py.

The problem this solves: a run can finish with exit code 0 — and the UI can
say "completed successfully" — while almost nothing actually happened.
main.py deliberately keeps going when a step fails (one broken step shouldn't
abort the rest), so every failure is logged and swallowed. Nothing ever added
those failures up. A real run against a document with unrecognized headings
logged 12 errors and silently skipped six workflows, and still exited 0.

RunIssueTracker listens to the log stream for the duration of a course and
counts ERROR-level records, plus explicit "document problems" main.py
registers for silent no-ops that don't log an error at all (e.g. the splitter
found zero units, so every later step quietly had nothing to do).
log_course_summary() then prints a clearly-marked block. Its first line
carries a machine-readable token — `estado=con_problemas` or `estado=ok` —
that the web UI reads to show "finished with problems" instead of success.
The exit code is deliberately left alone: partial success is a normal outcome
here, not a crash.

Errors from the optional AI layer are excluded: they fall back to the
deterministic parser by design and don't change what gets uploaded, so
counting them would flag every run as problematic whenever the AI is off or
its key is dead.
"""
import logging
import os
import threading

SUMMARY_PREFIX = "[RESUMEN]"
STATE_OK = "estado=ok"
STATE_PROBLEMS = "estado=con_problemas"

_AI_LOGGER_PREFIXES = (
    "core.ai_", "core.parser_validator", "core.document_splitter",
    "google_genai", "httpx",
)
_AI_MESSAGE_MARKERS = (
    "AI QA Layer", "AI Validation workflow failed", "Silent AI validation failed",
    "AI parsing failed", "AI QA Warning",
)


class RunIssueTracker(logging.Handler):
    """Attach to the root logger; call reset() at the start of each course."""

    def __init__(self):
        super().__init__(level=logging.ERROR)
        self._data_lock = threading.Lock()
        self.errors = []            # [(logger_name, first_line_of_message)]
        self.document_issues = []   # [message]

    def emit(self, record):
        try:
            if record.name.startswith(_AI_LOGGER_PREFIXES):
                return
            message = record.getMessage().strip()
            # logger.error(traceback.format_exc()) always follows a real error
            # line that was already counted — don't count the traceback twice.
            if not message or message.startswith("Traceback (most recent call last)"):
                return
            if any(marker in message for marker in _AI_MESSAGE_MARKERS):
                return
            with self._data_lock:
                self.errors.append((record.name, message.splitlines()[0]))
        except Exception:
            self.handleError(record)

    def note_document_issue(self, message: str):
        with self._data_lock:
            self.document_issues.append(message)

    def reset(self):
        with self._data_lock:
            self.errors.clear()
            self.document_issues.clear()

    def summary_lines(self, course_id, max_items: int = 15):
        """Returns (has_problems, [lines]). Every line starts with SUMMARY_PREFIX."""
        with self._data_lock:
            docs = list(self.document_issues)
            errs = list(self.errors)

        if not docs and not errs:
            return False, [f"{SUMMARY_PREFIX} Curso {course_id} | {STATE_OK} | Completado sin errores."]

        lines = [
            f"{SUMMARY_PREFIX} Curso {course_id} | {STATE_PROBLEMS} | "
            f"{len(docs)} problema(s) del documento, {len(errs)} error(es) durante la ejecución. "
            f"Revisa el detalle antes de dar el curso por listo."
        ]
        for issue in docs:
            lines.append(f"{SUMMARY_PREFIX}   - Documento: {issue}")

        counts = {}
        for name, msg in errs:
            counts[(name, msg)] = counts.get((name, msg), 0) + 1
        for shown, ((name, msg), n) in enumerate(counts.items()):
            if shown >= max_items:
                lines.append(f"{SUMMARY_PREFIX}   - ... y {len(counts) - max_items} error(es) distinto(s) más (ver la terminal).")
                break
            lines.append(f"{SUMMARY_PREFIX}   - [{name}] {msg}" + (f" (x{n})" if n > 1 else ""))
        return True, lines


def log_course_summary(log: logging.Logger, tracker: RunIssueTracker, course_id):
    """Logs the summary block: WARNING when there are problems, INFO when clean."""
    has_problems, lines = tracker.summary_lines(course_id)
    emit = log.warning if has_problems else log.info
    for line in lines:
        emit(line)
    return has_problems


def check_document_outputs(log: logging.Logger, tracker: RunIssueTracker, course_id, manifest, workspace_dir):
    """
    Flags the failures that leave no error in the log: the splitter ran
    without complaint but found nothing, so every later step quietly has
    nothing to process. `manifest` is what run_docx_splitting_workflow()
    returns; None means splitting didn't run (disabled), so nothing is checked.
    """
    if manifest is None:
        return

    if not any(manifest.values()):
        msg = (
            "No se detectó ninguna Unidad ni Actividad en el documento. Se reconocen los "
            "encabezados 'UNIDAD DIDÁCTICA N' y 'UNIDAD N.' (solo si está sola en su fila). "
            "Los pasos que dependen de la estructura del documento (secciones de unidad, "
            "actividades, rúbricas, cuestionarios, materiales, introducciones de unidad) "
            "no tendrán nada que procesar."
        )
        tracker.note_document_issue(msg)
        log.warning(f"[DOCUMENTO] {msg}")

    intro_path = os.path.join(workspace_dir, str(course_id), "introduccion", "introduccion_general.html")
    if not os.path.exists(intro_path):
        msg = (
            "No se extrajo la Introducción General (no se encontró el encabezado "
            "'PRESENTACIÓN DEL ESPACIO ACADÉMICO'); la actividad quedará vacía en Moodle."
        )
        tracker.note_document_issue(msg)
        log.warning(f"[DOCUMENTO] {msg}")
