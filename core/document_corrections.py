"""
Choices the user makes in the document review panel that change what gets
uploaded (as opposed to "Ignorar", which only acknowledges a problem).

For a block of the document no unit/activity claimed, the user can:

1. Turn it into a new activity of a chosen type ({"tipo": "Foro"}) —
   "Foro 1. …", "Proyecto de Clase (Final): …". The pipeline identifies
   regular activities by their "ACTIVIDAD N" number everywhere (fragment
   file, Moodle name, rubric, quiz questions, exclusion list). These blocks
   have no such number, so they're "extra" activities identified by their
   document heading.
2. Add it to an existing activity ({"agregar_a": N}) — e.g. a set of
   questions that belongs to Actividad 6. Its content is appended to
   actividades/actividadN.html, so every later step treats it as part of
   that activity with no special handling.

Files (all under workspace/<id>/):
- corrections.json — the choices, keyed by the review's problem id for the
  block (stable for the same document).
- actividades_extra/ — written by the splitter on every run: one HTML
  fragment per new activity plus manifest.json, and anexos.json for blocks
  added to existing activities. Read by the Moodle structure step (creates
  the activity, named after the heading, in its document position), the
  content upload, the rubric upload (Tarea) and the quiz export (Cuestionario).

corrections.json lives in the course folder, which is wiped when a new
document is uploaded, so choices never carry over to a different document.
"""
import json
import logging
import os
import re
import shutil

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

EXTRA_DIR = "actividades_extra"
_MANIFEST = "manifest.json"
_APPENDED = "anexos.json"
_MAX_NAME = 250  # Moodle activity names are limited to 255 characters


def _corrections_path(course_id) -> str:
    return os.path.join("workspace", str(course_id), "corrections.json")


def get_corrections(course_id) -> dict:
    """{"bloques": {problem_id: {"tipo": "Foro"} | {"agregar_a": 6}}}; empty when nothing was chosen."""
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


def set_block_choice(course_id, issue_id: str, choice) -> None:
    """
    choice: {"tipo": "Foro" | "Tarea" | "Cuestionario"} to make the block a new
    activity, {"agregar_a": N} to add it to Actividad N, or None to undo.
    """
    from core.document_coverage import ACTIVITY_TYPES
    if choice is not None:
        if set(choice) == {"tipo"}:
            if choice["tipo"] not in ACTIVITY_TYPES:
                raise ValueError(f"Tipo de actividad no válido: {choice['tipo']}")
        elif set(choice) == {"agregar_a"}:
            if not isinstance(choice["agregar_a"], int) or isinstance(choice["agregar_a"], bool) or choice["agregar_a"] < 1:
                raise ValueError(f"Número de actividad no válido: {choice['agregar_a']}")
        else:
            raise ValueError(f"Corrección no válida: {choice}")
    corrections = get_corrections(course_id)
    if choice is None:
        corrections["bloques"].pop(issue_id, None)
    else:
        corrections["bloques"][issue_id] = dict(choice)
    path = _corrections_path(course_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(corrections, f, ensure_ascii=False, indent=2)


def set_block_activity(course_id, issue_id: str, tipo) -> None:
    """Shorthand: make the block a new activity of `tipo`, or undo with None."""
    set_block_choice(course_id, issue_id, None if tipo is None else {"tipo": tipo})


def _heading(first_row) -> str:
    """The block's heading: the first non-empty paragraph of its first row."""
    for el in first_row.find_all(["p", "h1", "h2", "h3", "h4", "li"]):
        text = " ".join(el.get_text(" ").split())
        if text:
            return text
    return " ".join(first_row.get_text(" ").split())


def _cells_html(rows) -> str:
    return "".join(td.decode_contents() for tr in rows for td in tr.find_all(["td", "th"], recursive=False))


def _fragment_html(rows, heading: str = None) -> str:
    """Same shape as the splitter's activity fragments: cell contents, headings as <p><b>, title removed if given."""
    soup = BeautifulSoup(_cells_html(rows), "html.parser")
    if heading:
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


def _next_activity_in_unit(row_roles, after_row: int, unit):
    """Number of the first regular activity after `after_row` in the same unit, or None."""
    for role in row_roles[after_row + 1:]:
        if role and role["role"] == "unit":
            return None
        if role and role["role"] == "activity" and role["heading"] and role["unit"] == unit:
            return role["activity"]
    return None


def _activity_file(activity_manifest: dict, number: int):
    for acts in (activity_manifest or {}).values():
        info = acts.get(str(number))
        if info and info.get("file"):
            return info["file"]
    return None


def write_extra_activities(course_id, trs, row_roles, base_dir: str, activity_manifest: dict = None) -> list:
    """
    Called by the splitter after it has walked the document and written the
    regular activities. Rewrites actividades_extra/ from scratch so an undone
    choice leaves nothing behind. Returns the new-activity manifest entries.
    """
    from core.data_parser import merge_material_de_referencia

    extra_dir = os.path.join(base_dir, EXTRA_DIR)
    shutil.rmtree(extra_dir, ignore_errors=True)
    chosen = get_corrections(course_id)["bloques"]
    if not chosen:
        return []

    from core.document_coverage import find_unassigned_blocks
    from core.docx_rubrica_parser import parse_rubrica_from_fragment

    os.makedirs(extra_dir, exist_ok=True)
    material_dir = os.path.join(base_dir, "material")
    entries, appended, names = [], [], set()
    for block in find_unassigned_blocks(trs, row_roles):
        choice = chosen.get(block["problema"])
        if not choice:
            continue
        rows = trs[block["fila_inicio"]:block["fila_fin"] + 1]
        raw_block = _cells_html(rows)

        if "agregar_a" in choice:
            number = choice["agregar_a"]
            filename = _activity_file(activity_manifest, number)
            if not filename:
                logger.warning(f"  No existe la Actividad {number} para añadirle un bloque (se ignora): {block['problema']}")
                continue
            with open(os.path.join(base_dir, "actividades", filename), "a", encoding="utf-8") as f:
                f.write(_fragment_html(rows))
            unit = next((int(u) for u, acts in activity_manifest.items() if str(number) in acts), block["unidad"])
            # Its readings go to the unit's Material de referencia page, like
            # those of the activity it now belongs to.
            merge_material_de_referencia(raw_block, unit or 0, material_dir, str(number))
            appended.append({"issue_id": block["problema"], "actividad": number, "unidad": unit, "archivo": filename})
            logger.info(f"  ✓ Bloque añadido en la revisión a la Actividad {number} ({filename})")
            continue

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
        with open(os.path.join(extra_dir, f"{key}.html"), "w", encoding="utf-8") as f:
            f.write(_fragment_html(rows, heading))
        merge_material_de_referencia(raw_block, block["unidad"] or 0, material_dir, name)
        entries.append({
            "clave": key,
            "issue_id": block["problema"],
            "nombre": name,
            "tipo": choice["tipo"],
            "unidad": block["unidad"],
            "archivo": f"{key}.html",
            # Where it sits in the document: created right before this
            # activity in Moodle (None = at the end of its unit's section).
            "antes_de_actividad": _next_activity_in_unit(row_roles, block["fila_fin"], block["unidad"]),
            "rubrica": parse_rubrica_from_fragment(raw_block) if choice["tipo"] == "Tarea" else [],
        })
        logger.info(f"  ✓ Actividad añadida en la revisión: '{name}' ({choice['tipo']}, Unidad {block['unidad']}) -> {key}.html")

    used = {e["issue_id"] for e in entries} | {a["issue_id"] for a in appended}
    for issue_id in sorted(set(chosen) - used):
        logger.warning(f"  Corrección sin aplicar (el bloque ya no existe o la actividad destino no existe): {issue_id}")

    with open(os.path.join(extra_dir, _MANIFEST), "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    with open(os.path.join(extra_dir, _APPENDED), "w", encoding="utf-8") as f:
        json.dump(appended, f, ensure_ascii=False, indent=2)
    return entries


def _read_list(course_id, filename) -> list:
    path = os.path.join("workspace", str(course_id), EXTRA_DIR, filename)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"No se pudo leer {path}: {e}")
        return []


def get_extra_activities(course_id) -> list:
    """New activities the splitter last wrote, or [] if there are none."""
    return _read_list(course_id, _MANIFEST)


def get_appended_blocks(course_id) -> list:
    """Blocks the splitter last added to existing activities, or []."""
    return _read_list(course_id, _APPENDED)


def add_extra_activities_to_sections(sections: list, extras: list) -> list:
    """
    Adds each extra activity to its unit's section in the structure
    parse_raw_document() returned (section unit_number = unit + 1), right
    before the activity that follows it in the document, so Moodle shows it
    in document order on a new course. Returns the extras that had no
    matching section.
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
        new_activity = {"name": extra["nombre"], "type": extra["tipo"]}
        before = extra.get("antes_de_actividad")
        pattern = re.compile(rf"^\s*ACTIVIDAD\s*{before}\b", re.IGNORECASE) if before else None
        index = next((i for i, act in enumerate(section["activities"]) if pattern and pattern.match(act["name"])), None)
        if index is None:
            section["activities"].append(new_activity)
        else:
            section["activities"].insert(index, new_activity)
    return unplaced
