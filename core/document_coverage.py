"""
What the pipeline read from a course design document, and what it didn't.

The splitter (core/data_parser.py) walks every row of the document's tables
and silently skips the ones it doesn't recognize. A heading worded slightly
differently ("FORO 1." instead of "ACTIVIDAD 1.") therefore doesn't fail —
its whole block of content just never reaches Moodle, and nothing says so.

analyze_document() compares what was split against the expected structure
written down below, and returns:

- "bloques": the document as consecutive blocks of rows, each marked as read
  (a unit / an activity), known (a section the pipeline intentionally doesn't
  upload, e.g. the general-information table), or a problem (content that
  went nowhere).
- "problemas": everything that doesn't match the expected structure, each
  with a stable id so the user can mark it "ignorar" (see
  get_ignored_issues / set_ignored_issues) and the UI can block Run until
  every problem is fixed or ignored.

Nothing here changes what gets uploaded; it only reports.
"""
import hashlib
import json
import logging
import os
import re
import unicodedata

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# The expected structure of a course design document — the one place it's
# written down. Labels are matched accent-insensitively at the start of a row.
# ---------------------------------------------------------------------------

# Tables before the units: read by other steps (course name, overview), never
# uploaded as unit content. A row starting with one of these marks it and the
# rest of its table, until the next unit/activity row.
PREAMBLE_MARKERS = {
    "INFORMACION GENERAL": "informacion_general",
    "PLAN DE FORMACION": "plan_formacion",
    "GLOSARIO": "glosario",
}

# Rows every unit has between its heading and its activities. Resumen and
# preguntas orientadoras are uploaded by the unit-intro step
# (core/unidades_intro_parser.py); the others are just section titles.
UNIT_SECTION_LABELS = (
    "DESCRIPCION GENERAL",
    "RESUMEN",
    "PREGUNTAS ORIENTADORAS",
    "DETALLES DE LA UNIDAD",
    "ACTIVIDADES DE APRENDIZAJE",
)

# Rows that only ever appear inside an activity. Finding them in content no
# activity claimed means an activity heading wasn't recognized.
ACTIVITY_PART_LABELS = (
    "QUE VAMOS A LOGRAR",
    "COMO LO VAMOS A LOGRAR",
    "COMO LO VAMOS A EVALUAR",
    "INFORMACION PARA EL EQUIPO DE PRODUCCION",
    "HERRAMIENTAS DE LA PLATAFORMA VIRTUAL",
    "ELIJA LA HERRAMIENTA DE LA PLATAFORMA",
    "LISTA DE HERRAMIENTAS PARA DESARROLLAR",
    "LECTURAS PARA DESARROLLAR",
)

# Every unit must have these (keys of the review report's unit entry).
UNIT_REQUIRED_PARTS = {
    "resumen": "Resumen",
    "preguntas_orientadoras": "Preguntas orientadoras",
}

# Rubrics are uploaded to Moodle assignments only
# (actions/docx_rubrica_actions.py), so only these types need one.
TYPES_NEEDING_RUBRIC = {"Tarea"}

# Types the pipeline can't turn into a Moodle activity.
UNRESOLVED_TYPES = {"Desconocido", "No sabe"}

# Types a user can give an unrecognized block to turn it into an activity
# (core/document_corrections.py).
ACTIVITY_TYPES = ("Foro", "Tarea", "Cuestionario")

_PLAN_UNIT_RE = re.compile(r"^UNIDAD\s*(?:DIDACTICA\s*)?(\d+)")
_PLAN_ACTIVITY_START_RE = re.compile(r"^ACTIVIDAD\s+(\d+)\b")
_MAX_BLOCK_HTML = 200_000


def _norm(text: str) -> str:
    """Upper-case, accent-free, single-spaced, without leading ¿/¡."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.split()).upper().lstrip("¿¡ ")


def _row_text(tr) -> str:
    return " ".join(tr.get_text(" ").split())


def _starts_with_any(norm_text: str, labels) -> bool:
    return any(norm_text.startswith(label) for label in labels)


def _preamble_labels(trs, roles) -> list:
    labels = [None] * len(trs)
    table, mode = None, None
    for i, tr in enumerate(trs):
        if tr.find_parent("table") is not table:
            table, mode = tr.find_parent("table"), None
        if roles[i] is not None:
            mode = None
            continue
        norm = _norm(_row_text(tr))
        for marker, label in PREAMBLE_MARKERS.items():
            if norm.startswith(marker):
                mode = label
                break
        labels[i] = mode
    return labels


def _parse_plan(trs, preamble) -> dict:
    """
    {unit_number: [activity_numbers]} from the 'Plan de formación' overview
    table. Only text that STARTS a cell or paragraph counts: the overview's
    descriptions mention other activities in prose ("con base en la
    actividad 2…"), which must not be read as listing them.
    """
    plan, unit = {}, None
    for tr, label in zip(trs, preamble):
        if label != "plan_formacion":
            continue
        cells = tr.find_all(["td", "th"], recursive=False)
        if cells:
            m = _PLAN_UNIT_RE.match(_norm(cells[0].get_text(" ")))
            if m:
                unit = int(m.group(1))
                plan.setdefault(unit, [])
        if unit is None:
            continue
        for cell in cells:
            for piece in [cell] + cell.find_all(["p", "li"]):
                a = _PLAN_ACTIVITY_START_RE.match(_norm(piece.get_text(" ")))
                if a and int(a.group(1)) not in plan[unit]:
                    plan[unit].append(int(a.group(1)))
    return plan


def _row_kind(tr, role, preamble_label):
    """(kind, key, status) for one row. kind groups consecutive rows into a block."""
    if role and role["role"] == "unit":
        return "unidad", role["unit"], "ok"
    if role and role["role"] == "activity":
        return "actividad", (role["unit"], role["activity"]), "ok"
    if preamble_label:
        return preamble_label, None, "conocido"
    norm = _norm(_row_text(tr))
    if not norm:
        return None, None, None  # empty row: joins whichever block it sits in
    if _starts_with_any(norm, UNIT_SECTION_LABELS):
        return "seccion_unidad", None, "conocido"
    return "sin_asignar", None, "problema"


def _block_title(kind, key, first_row_text, unit):
    if kind == "unidad":
        return f"Unidad {key} (encabezado)"
    if kind == "actividad":
        return f"Actividad {key[1]} (Unidad {key[0]})"
    if kind == "seccion_unidad":
        return f"Secciones de la Unidad {unit}" if unit else "Secciones de unidad"
    if kind == "informacion_general":
        return "Información general del espacio académico"
    if kind == "plan_formacion":
        return "Plan de formación (tabla resumen)"
    if kind == "glosario":
        return "Glosario"
    return first_row_text[:90] + ("…" if len(first_row_text) > 90 else "")


def _build_blocks(trs, roles, preamble):
    blocks, current = [], None
    unit = None
    for i, tr in enumerate(trs):
        role = roles[i]
        if role and role.get("unit"):
            unit = role["unit"]
        kind, key, status = _row_kind(tr, role, preamble[i])
        if kind is None:
            if current:
                current["_rows"].append(i)
            continue
        starts_new = (
            current is None
            or current["tipo"] != kind
            or current["_key"] != key
            or (kind == "actividad" and role["heading"])  # a repeated activity number is its own block
            or (kind == "seccion_unidad" and current["unidad"] != unit)
        )
        if starts_new:
            current = {"tipo": kind, "_key": key, "estado": status, "unidad": unit, "_rows": [i]}
            blocks.append(current)
        else:
            current["_rows"].append(i)

    for n, b in enumerate(blocks):
        rows = b.pop("_rows")
        key = b.pop("_key")
        first_text = next((_row_text(trs[r]) for r in rows if _row_text(trs[r])), "")
        b["id"] = f"b{n}"
        b["titulo"] = _block_title(b["tipo"], key, first_text, b["unidad"])
        b["fila_inicio"], b["fila_fin"], b["n_filas"] = rows[0], rows[-1], len(rows)
        if b["tipo"] == "actividad":
            b["actividad"] = key[1]
        if b["estado"] == "problema":
            b["texto_normalizado"] = [_norm(_row_text(trs[r])) for r in rows]
            html = "".join(
                td.decode_contents()
                for r in rows
                for td in trs[r].find_all(["td", "th"], recursive=False)
            )
            b["html"] = html[:_MAX_BLOCK_HTML]
    return blocks


def _issue(kind, key, titulo, detalle, bloquea=True, **extra):
    """
    bloquea=True: content would be lost or wrong in Moodle — Run stays blocked
    until it's fixed in the .docx or ignored. bloquea=False: every piece of
    content was still read, only the document disagrees with itself (e.g. the
    overview table lists an activity under a different unit) — shown, never
    blocks.
    """
    return {"id": f"{kind}:{key}", "tipo": kind, "titulo": titulo, "detalle": detalle, "bloquea": bloquea, **extra}


def _block_issues(blocks):
    issues, seen = [], {}
    for b in blocks:
        if b["estado"] != "problema":
            continue
        norm_rows = b.pop("texto_normalizado")
        digest = hashlib.sha1(" | ".join(norm_rows[:3]).encode("utf-8")).hexdigest()[:10]
        seen[digest] = seen.get(digest, 0) + 1
        key = digest if seen[digest] == 1 else f"{digest}-{seen[digest]}"
        where = f"Unidad {b['unidad']}" if b["unidad"] else "antes de la primera unidad"
        looks_like_activity = sum(1 for t in norm_rows if _starts_with_any(t, ACTIVITY_PART_LABELS))
        if looks_like_activity:
            from core.data_parser import detect_activity_type
            suggested = detect_activity_type(" ".join(norm_rows))
            issue = _issue(
                "actividad_no_reconocida", key,
                f"Posible actividad no reconocida: «{b['titulo']}»",
                f"{b['n_filas']} fila(s) en {where} tienen la forma de una actividad "
                f"(«¿Qué vamos a lograr?», herramientas de la plataforma…), pero su "
                f"encabezado no empieza con «ACTIVIDAD N», así que su contenido no se subirá.",
                bloque=b["id"], unidad=b["unidad"],
                tipo_sugerido=suggested if suggested in ACTIVITY_TYPES else None,
            )
        else:
            issue = _issue(
                "contenido_sin_asignar", key,
                f"Contenido sin asignar: «{b['titulo']}»",
                f"{b['n_filas']} fila(s) en {where} no pertenecen a ninguna unidad ni "
                f"actividad reconocida, así que no se subirán.",
                bloque=b["id"], unidad=b["unidad"],
            )
        b["problema"] = issue["id"]
        issues.append(issue)
    return issues


_MAX_LISTED_QUESTIONS = 30


def _quiz_issue(key: str, label: str, summary, **extra):
    """
    The problem to report for one Cuestionario, or None. `summary` is
    actions.html_transformer.summarize_quiz(): questions read vs. the number
    the document evidently has (stated, one per "Respuesta correcta", or
    "¿…?" lines that didn't become questions).
    """
    if not summary:
        return None
    read, expected, unread = summary["encontradas"], summary["esperadas"], summary["no_leidas"]
    hints = (
        "Puede que las preguntas estén escritas en un formato que el lector de preguntas no "
        "reconoce (revisa «Ver parseo» de la actividad), o que estén en un bloque sin asignar: "
        "en ese caso usa «Añadir a una actividad existente» en ese bloque."
    )
    listed = {"preguntas_no_leidas": unread[:_MAX_LISTED_QUESTIONS], "preguntas_leidas": read, "preguntas_esperadas": expected}
    if read == 0:
        return _issue(
            "cuestionario_sin_preguntas", key,
            f"{label} (Cuestionario): sin preguntas" + (f" (el documento tiene {expected})" if expected else ""),
            f"No se reconoció ninguna pregunta, así que el cuestionario quedará vacío en Moodle. {hints}",
            **listed, **extra,
        )
    if read < expected:
        return _issue(
            "cuestionario_preguntas_incompletas", key,
            f"{label} (Cuestionario): se leyeron {read} de {expected} preguntas",
            f"Solo se subirán {read} pregunta(s); el documento tiene al menos {expected}. {hints}",
            **listed, **extra,
        )
    return None


def find_unassigned_blocks(trs, row_roles) -> list:
    """
    The blocks of rows no unit/activity claimed, each with the id of the
    problem the review reports for it ("problema") and its row range. The id
    is what the user's choices in the review panel are keyed by, so this is
    the one place both the review and the corrections find blocks.
    """
    blocks = _build_blocks(trs, row_roles, _preamble_labels(trs, row_roles))
    _block_issues(blocks)
    return [b for b in blocks if b["estado"] == "problema"]


def failed_analysis(reason: str) -> dict:
    """An analysis that couldn't run is itself a problem to resolve, never a clean result."""
    return {
        "bloques": [],
        "plan": {},
        "problemas": [_issue(
            "analisis_fallido", "doc",
            "No se pudo revisar la estructura del documento",
            f"{reason} No hay forma de saber qué contenido se leyó y cuál no.",
        )],
    }


def analyze_document(html: str, manifest: dict, row_roles: list, report: dict, rubricas: dict,
                     extras: list = None, appended: list = None, quiz_info: dict = None) -> dict:
    """
    html: raw_docx_extracted.html. manifest / row_roles: what
    run_docx_splitting_workflow returned / filled in for that same HTML.
    report: the review report (for resumen / preguntas per unit).
    rubricas: parse_rubricas_from_html(html).
    extras / appended: the blocks the user turned into activities or added to
    an existing one (core/document_corrections) — their problems are
    reported as resolved ("resuelto") instead of open.
    quiz_info: actions.html_transformer.summarize_quiz() per quiz, keyed
    "a<N>" for Actividad N and "x<issue hash>" for a quiz created in the
    review. None skips the question checks.
    """
    soup = BeautifulSoup(html, "html.parser")
    from core.data_parser import top_level_rows
    trs = top_level_rows(soup)
    if len(row_roles) != len(trs):
        logger.error(f"Cobertura: {len(row_roles)} roles para {len(trs)} filas; se omite el análisis.")
        return failed_analysis("El análisis no coincide con las filas del documento (¿falló la división del documento?).")

    preamble = _preamble_labels(trs, row_roles)
    blocks = _build_blocks(trs, row_roles, preamble)
    issues = _block_issues(blocks)

    extras_by_issue = {e["issue_id"]: e for e in (extras or [])}
    appended_by_issue = {a["issue_id"]: a for a in (appended or [])}
    for issue in issues:
        extra = extras_by_issue.get(issue["id"])
        added = appended_by_issue.get(issue["id"])
        if not (extra or added):
            continue
        block = next(b for b in blocks if b["id"] == issue["bloque"])
        block["estado"] = "corregido"
        if extra:
            issue["resuelto"] = {"accion": "crear", **{k: extra[k] for k in ("tipo", "nombre", "unidad", "archivo")}}
            block["titulo"] = f"{extra['nombre']} ({extra['tipo']}, añadida en la revisión)"
        else:
            issue["resuelto"] = {"accion": "agregar", **{k: added[k] for k in ("actividad", "unidad", "archivo")}}
            block["titulo"] = f"{block['titulo']} (añadido a la Actividad {added['actividad']} en la revisión)"
    for extra in extras or []:
        issue_hash = extra["issue_id"].split(":", 1)[1]
        quiz_issue = _quiz_issue("x" + issue_hash, f"«{extra['nombre']}»", (quiz_info or {}).get("x" + issue_hash),
                                 unidad=extra["unidad"]) if extra["tipo"] == "Cuestionario" else None
        if quiz_issue:
            issues.append(quiz_issue)
        if extra["tipo"] in TYPES_NEEDING_RUBRIC and not extra.get("rubrica"):
            issues.append(_issue(
                "rubrica_faltante", "x" + extra["issue_id"].split(":", 1)[1],
                f"«{extra['nombre']}» ({extra['tipo']}): sin rúbrica",
                "No se encontró una tabla de «Criterios de desempeño» en este bloque, "
                "así que no se subirá ninguna rúbrica.",
                unidad=extra["unidad"],
            ))

    # Where each unit's resumen / preguntas rows physically are, and what
    # kind of cell they start with — to explain *why* one wasn't read.
    unit_part_rows, unit = {}, None
    part_labels = {"resumen": "RESUMEN", "preguntas_orientadoras": "PREGUNTAS ORIENTADORAS"}
    for tr, role in zip(trs, row_roles):
        if role and role.get("unit"):
            unit = role["unit"]
            continue
        norm = _norm(_row_text(tr))
        first_cell = tr.find(["td", "th"], recursive=False)
        for part, label in part_labels.items():
            if unit and norm.startswith(label) and first_cell is not None:
                unit_part_rows.setdefault((unit, part), first_cell.name)

    # An activity whose rows contain a second "¿Qué vamos a lograr?" swallowed
    # the next block: its heading ("FORO 2.", …) isn't a stop condition for
    # the splitter, so that content is uploaded inside this activity.
    for b in blocks:
        if b["tipo"] != "actividad":
            continue
        starts = [r for r in range(b["fila_inicio"], b["fila_fin"] + 1)
                  if _norm(_row_text(trs[r])).startswith(ACTIVITY_PART_LABELS[0])]
        for second in starts[1:]:
            heading_row = second - 1
            heading = _row_text(trs[heading_row]) if heading_row > b["fila_inicio"] else ""
            key = hashlib.sha1(_norm(heading or str(second)).encode("utf-8")).hexdigest()[:10]
            issues.append(_issue(
                "actividad_fusionada", f"a{b['actividad']}-{key}",
                f"Actividad {b['actividad']} parece contener otra actividad"
                + (f": «{heading[:90]}»" if heading else ""),
                "Dentro de esta actividad aparece un segundo «¿Qué vamos a lograr?». Su encabezado no se "
                "reconoce como el inicio de una actividad, así que ese contenido se subirá dentro de la "
                f"Actividad {b['actividad']}. Corrige el encabezado en el .docx (p. ej. «ACTIVIDAD N.») o ignóralo.",
                actividad=b["actividad"], unidad=b["unidad"],
            ))

    found = {}  # activity -> unit, as split
    for unit_key, acts in (manifest or {}).items():
        for act_key in acts:
            found[int(act_key)] = int(unit_key)
    found_units = {r["unit"] for r in row_roles if r and r["role"] == "unit"} | set(found.values())

    # Activity numbers the splitter saw more than once (the later one is
    # written to actividadN_1.html and the manifest keeps only one of them).
    headings = {}
    for r in row_roles:
        if r and r["role"] == "activity" and r["heading"]:
            headings[r["activity"]] = headings.get(r["activity"], 0) + 1
    for act, n in sorted(headings.items()):
        if n > 1:
            issues.append(_issue(
                "actividad_duplicada", f"a{act}",
                f"«Actividad {act}» aparece {n} veces",
                "El documento tiene más de un encabezado con el mismo número de actividad; "
                "solo una de ellas se tendrá en cuenta al subir.",
                actividad=act,
            ))

    for unit_key, acts in sorted((manifest or {}).items(), key=lambda kv: int(kv[0])):
        for act_key, info in sorted(acts.items(), key=lambda kv: int(kv[0])):
            act = int(act_key)
            if info.get("tipo") in UNRESOLVED_TYPES:
                issues.append(_issue(
                    "tipo_desconocido", f"a{act}",
                    f"Actividad {act}: tipo sin definir ({info.get('tipo')})",
                    "No se encontró una herramienta marcada con X (Foro, Tarea, Cuestionario…) "
                    "en la tabla «Herramientas de la plataforma virtual» de esta actividad.",
                    actividad=act, unidad=int(unit_key),
                ))
            quiz_issue = _quiz_issue(f"a{act}", f"Actividad {act}", (quiz_info or {}).get(f"a{act}"),
                                     actividad=act, unidad=int(unit_key)) if info.get("tipo") == "Cuestionario" else None
            if quiz_issue:
                issues.append(quiz_issue)
            if info.get("tipo") in TYPES_NEEDING_RUBRIC and act not in rubricas:
                issues.append(_issue(
                    "rubrica_faltante", f"a{act}",
                    f"Actividad {act} ({info['tipo']}): sin rúbrica",
                    "No se encontró una tabla de «Criterios de desempeño» con «Puntos» en esta actividad, "
                    "así que no se subirá ninguna rúbrica.",
                    actividad=act, unidad=int(unit_key),
                ))

    for unit_key, unit in sorted((report.get("unidades") or {}).items(), key=lambda kv: int(kv[0])):
        if not unit.get("actividades"):
            issues.append(_issue(
                "unidad_sin_actividades", f"u{unit_key}",
                f"Unidad {unit_key}: sin actividades",
                "Se encontró el encabezado de la unidad, pero ninguna actividad reconocida dentro de ella.",
                unidad=int(unit_key),
            ))
        for part, label in UNIT_REQUIRED_PARTS.items():
            if not (unit.get(part) or {}).get("encontrado"):
                cell = unit_part_rows.get((int(unit_key), part))
                if cell == "th":
                    detalle = (f"La fila «{label}» existe, pero sus celdas son de tipo encabezado "
                               f"(<th>) y el paso que sube la introducción de la unidad solo lee "
                               f"celdas normales, así que no se subirá.")
                elif cell:
                    detalle = f"La fila «{label}» existe, pero no se pudo leer su contenido."
                else:
                    detalle = f"No se encontró la fila «{label}» de esta unidad."
                issues.append(_issue(
                    f"unidad_sin_{part}", f"u{unit_key}",
                    f"Unidad {unit_key}: «{label}» no se subirá",
                    detalle, unidad=int(unit_key),
                ))

    plan = _parse_plan(trs, preamble)
    if plan:
        for unit in sorted(set(plan) - found_units):
            issues.append(_issue(
                "unidad_no_encontrada", f"u{unit}",
                f"Unidad {unit}: está en el Plan de formación pero no en el documento",
                "La tabla resumen lista esta unidad, pero no se reconoció su encabezado "
                "(«UNIDAD DIDÁCTICA N» o «UNIDAD N.» sola en su fila).",
                unidad=unit,
            ))
        planned = {}
        for unit, acts in plan.items():
            for act in acts:
                planned[act] = unit
        for act, unit in sorted(planned.items()):
            if act not in found:
                issues.append(_issue(
                    "actividad_no_encontrada", f"a{act}",
                    f"Actividad {act}: está en el Plan de formación pero no se encontró",
                    f"La tabla resumen la lista en la Unidad {unit}, pero no se reconoció "
                    f"ningún encabezado «ACTIVIDAD {act}» en el contenido.",
                    actividad=act, unidad=unit,
                ))
            elif found[act] != unit:
                issues.append(_issue(
                    "actividad_en_otra_unidad", f"a{act}",
                    f"Actividad {act}: en otra unidad que en el Plan de formación",
                    f"La tabla resumen la ubica en la Unidad {unit}, pero en el contenido "
                    f"aparece dentro de la Unidad {found[act]}. Se subirá en la Unidad {found[act]}.",
                    bloquea=False, actividad=act, unidad=found[act],
                ))
        for act, unit in sorted(found.items()):
            if act not in planned:
                issues.append(_issue(
                    "actividad_fuera_del_plan", f"a{act}",
                    f"Actividad {act}: no aparece en el Plan de formación",
                    f"Se encontró y se subirá en la Unidad {unit}, pero la tabla resumen no la "
                    f"lista como «Actividad {act}» (quizá con otro nombre).",
                    bloquea=False, actividad=act, unidad=unit,
                ))
    elif found_units:
        issues.append(_issue(
            "plan_no_encontrado", "doc",
            "No se encontró el «Plan de formación»",
            "Sin la tabla resumen no se puede comprobar que estén todas las unidades y actividades.",
        ))

    return {
        "plan": {str(u): acts for u, acts in sorted(plan.items())},
        "bloques": blocks,
        "problemas": issues,
    }


# ---------------------------------------------------------------------------
# "Ignorar" choices, per course — same storage pattern as
# core/activity_selection.py. Cleared with the rest of the course folder when
# a new document is uploaded, so ignores never carry over to a new document.
# ---------------------------------------------------------------------------

def _ignored_path(course_id) -> str:
    return os.path.join("workspace", str(course_id), "ignored_issues.json")


def get_ignored_issues(course_id) -> set:
    path = _ignored_path(course_id)
    if not os.path.exists(path):
        return set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            return {str(x) for x in json.load(f).get("ignored", [])}
    except Exception as e:
        # Fails closed on purpose (the opposite of activity_selection): a
        # corrupt file means problems show up as unresolved again, never
        # silently hidden.
        logger.error(f"No se pudo leer ignored_issues.json para el curso {course_id}: {e}.")
        return set()


def set_ignored_issues(course_id, ignored) -> None:
    path = _ignored_path(course_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"ignored": sorted({str(x) for x in ignored})}, f, ensure_ascii=False, indent=2)
