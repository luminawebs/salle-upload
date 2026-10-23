"""
Lets a user exclude specific activities (e.g. "don't upload Actividad 3")
from the automation run for a given course, without touching the global
ENABLE_* feature flags (which turn whole workflow steps on/off, not
individual activities).

The choice is stored per-course at workspace/<course_id>/skip_activities.json
so it survives across the preview -> configure -> run flow in the UI, the
same way other per-course state (contenidos.json, raw_docx_extracted.html)
already does.
"""
import os
import json
import logging

logger = logging.getLogger(__name__)


def _skip_file_path(course_id) -> str:
    return os.path.join("workspace", str(course_id), "skip_activities.json")


def get_skipped_activities(course_id) -> set:
    """
    Returns the set of activity numbers (as strings, e.g. {"3", "5"}) the
    user chose to exclude for this course. Fails open: a missing or corrupt
    file returns an empty set (skip nothing) so a bug here can never
    silently suppress an upload that would otherwise have happened —
    the pre-existing "process everything" behavior is always the fallback.
    """
    path = _skip_file_path(course_id)
    if not os.path.exists(path):
        return set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {str(x) for x in data.get("skipped", [])}
    except Exception as e:
        logger.error(f"No se pudo leer skip_activities.json para el curso {course_id}: {e}. Se procesarán todas las actividades.")
        return set()


def set_skipped_activities(course_id, skipped) -> None:
    """Persists the given collection of activity numbers as the skip list for this course."""
    path = _skip_file_path(course_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"skipped": sorted({str(x) for x in skipped})}, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# The whole glossary, included or excluded from the upload (one checkbox in
# the review; no per-term choice). Same storage pattern and the same
# fail-open fallback: a missing or corrupt file means "upload it".
# ---------------------------------------------------------------------------

def _glossary_file_path(course_id) -> str:
    return os.path.join("workspace", str(course_id), "skip_glosario.json")


def is_glossary_excluded(course_id) -> bool:
    """True when the user chose not to upload this course's glossary."""
    path = _glossary_file_path(course_id)
    if not os.path.exists(path):
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f).get("excluido") is True
    except Exception as e:
        logger.error(f"No se pudo leer skip_glosario.json para el curso {course_id}: {e}. Se subirá el glosario.")
        return False


def set_glossary_excluded(course_id, excluded: bool) -> None:
    path = _glossary_file_path(course_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"excluido": bool(excluded)}, f, ensure_ascii=False, indent=2)
