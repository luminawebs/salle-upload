"""
Choices the user makes in the document review panel that change what gets
uploaded (as opposed to "Ignorar", which only acknowledges a problem).

Today: turning an unrecognized block ("Foro 1. …", "Proyecto de Clase
(Final): …") into an activity of a chosen type. The pipeline identifies
regular activities by their "ACTIVIDAD N" number everywhere (fragment file,
Moodle name, rubric, exclusion list). These blocks have no such number, so
they're handled as "extra" activities, identified by their document heading:

- workspace/<id>/corrections.json — the choices, keyed by the review's
  problem id for the block (stable for the same document).
- workspace/<id>/actividades_extra/ — written by the splitter on every run:
  one HTML fragment per chosen block plus manifest.json. Read by the Moodle
  structure step (creates the activity, named after the heading), the
  content upload (fills its description) and the rubric upload (Tarea only).

corrections.json lives in the course folder, which is wiped when a new
document is uploaded, so choices never carry over to a different document.
"""
import json
import logging
import os
import shutil

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

EXTRA_DIR = "actividades_extra"
_MANIFEST = "manifest.json"
_MAX_NAME = 250  # Moodle activity names are limited to 255 characters


def _corrections_path(course_id) -> str:
    return os.path.join("workspace", str(course_id), "corrections.json")


def get_corrections(course_id) -> dict:
    """{"bloques": {problem_id: {"tipo": "Foro"}}}; empty when nothing was chosen."""
    path = _corrections_path(course_id)
    if not os.path.exists(path):
        return {"bloques": {}}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {"bloques": dict(data.get("bloques", {}))}
    except Exception as e:
        logger.error(f"No se pudo leer corrections.json para el curso {course_id}: {e}.")
        return {"bloques": {}}


def set_block_activity(course_id, issue_id: str, tipo) -> None:
    """Marks the block behind `issue_id` as an activity of `tipo`, or clears it when tipo is None."""
    from core.document_coverage import ACTIVITY_TYPES
    if tipo is not None and tipo not in ACTIVITY_TYPES:
        raise ValueError(f"Tipo de actividad no válido: {tipo}")
    corrections = get_corrections(course_id)
    if tipo is None:
        corrections["bloques"].pop(issue_id, None)
    else:
        corrections["bloques"][issue_id] = {"tipo": tipo}
    path = _corrections_path(course_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(corrections, f, ensure_ascii=False, indent=2)


def _heading(first_row) -> str:
    """The block's heading: the first non-empty paragraph of its first row."""
    for el in first_row.find_all(["p", "h1", "h2", "h3", "h4", "li"]):
        text = " ".join(el.get_text(" ").split())
        if text:
            return text
    return " ".join(first_row.get_text(" ").split())


def _fragment_html(rows, heading: str) -> str:
    """Same shape as the splitter's activity fragments: cell contents, title removed, headings as <p><b>."""
    html = "".join(td.decode_contents() for tr in rows for td in tr.find_all(["td", "th"], recursive=False))
    soup = BeautifulSoup(html, "html.parser")
    for el in soup.find_all(["p", "h1", "h2", "h3", "h4"]):
        if " ".join(el.get_text(" ").split()) == heading:
            el.decompose()
            break
    for header in soup.find_all(["h1", "h2", "h3"]):
        new_p = soup.new_tag("p")
        new_b = soup.new_tag("b")
        new_b.extend(header.contents)
        new_p.append(new_b)
        header.replace_with(new_p)
    return str(soup)


def write_extra_activities(course_id, trs, row_roles, base_dir: str) -> list:
    """
    Called by the splitter after it has walked the document. Rewrites
    actividades_extra/ from scratch so an undone choice leaves nothing behind.
    Returns the manifest entries.
    """
    extra_dir = os.path.join(base_dir, EXTRA_DIR)
    shutil.rmtree(extra_dir, ignore_errors=True)
    chosen = get_corrections(course_id)["bloques"]
    if not chosen:
        return []

    from core.document_coverage import find_unassigned_blocks
    from core.docx_rubrica_parser import parse_rubrica_from_fragment

    os.makedirs(extra_dir, exist_ok=True)
    entries, names = [], set()
    for block in find_unassigned_blocks(trs, row_roles):
        choice = chosen.get(block["problema"])
        if not choice:
            continue
        rows = trs[block["fila_inicio"]:block["fila_fin"] + 1]
        heading = _heading(rows[0])
        name = heading[:_MAX_NAME]
        # Two blocks with the same heading would become two Moodle activities
        # with the same name, and the upload could only ever find the first.
        n = 2
        while name.lower() in names:
            suffix = f" ({n})"
            name = heading[:_MAX_NAME - len(suffix)] + suffix
            n += 1
        names.add(name.lower())

        key = f"extra{len(entries) + 1}"
        fragment = _fragment_html(rows, heading)
        with open(os.path.join(extra_dir, f"{key}.html"), "w", encoding="utf-8") as f:
            f.write(fragment)
        raw_block = "".join(td.decode_contents() for tr in rows for td in tr.find_all(["td", "th"], recursive=False))
        entries.append({
            "clave": key,
            "issue_id": block["problema"],
            "nombre": name,
            "tipo": choice["tipo"],
            "unidad": block["unidad"],
            "archivo": f"{key}.html",
            "rubrica": parse_rubrica_from_fragment(raw_block) if choice["tipo"] == "Tarea" else [],
        })
        logger.info(f"  ✓ Actividad añadida en la revisión: '{name}' ({choice['tipo']}, Unidad {block['unidad']}) -> {key}.html")

    missing = set(chosen) - {e["issue_id"] for e in entries}
    for issue_id in sorted(missing):
        logger.warning(f"  Corrección sin bloque correspondiente en el documento (se ignora): {issue_id}")

    with open(os.path.join(extra_dir, _MANIFEST), "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    return entries


def get_extra_activities(course_id) -> list:
    """The manifest the splitter last wrote, or [] if there are no extra activities."""
    path = os.path.join("workspace", str(course_id), EXTRA_DIR, _MANIFEST)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"No se pudo leer {path}: {e}")
        return []


def add_extra_activities_to_sections(sections: list, extras: list) -> list:
    """
    Adds each extra activity to its unit's section in the structure
    parse_raw_document() returned (section unit_number = unit + 1). Returns
    the extras that had no matching section.
    """
    unplaced = []
    for extra in extras:
        # A block before the first unit has no unit; section 1 is
        # "Generalidades", not a unit, so it's left unplaced rather than guessed.
        unit = extra.get("unidad")
        section = next((s for s in sections if unit and s.get("unit_number") == unit + 1), None)
        if section is None:
            unplaced.append(extra)
            continue
        section["activities"].append({"name": extra["nombre"], "type": extra["tipo"]})
    return unplaced
