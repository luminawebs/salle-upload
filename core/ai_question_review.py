"""
Phase 2 of the AI quiz-question reader: the user reviews what the AI found.

The AI's reading of a quiz (core/ai_question_shadow.py, already verified word
for word against the document) becomes a list of proposals — a question the
parser missed, a correct answer it couldn't read, an item that isn't really a
question — and the user accepts or discards each one in "Vista previa". Only
accepted proposals change what uploads: the quiz questions (final_questions)
and the quiz description, which must not show the questions to students
(strip_accepted_questions). Nothing the AI says reaches Moodle unseen.

Decisions are stored per activity file in workspace/<course>/ai_decisions.json,
tied to the hash of the activity's HTML: if the document changes, the old
proposal and its decisions no longer apply.
"""
import html as html_lib
import json
import logging
import os
import re

from bs4 import BeautifulSoup

from core import ai_question_shadow as shadow

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DECISIONS_FILE = "ai_decisions.json"
DECISIONS = ("aceptar", "descartar")

# What each kind of proposal means to the user (shown in the UI).
KIND_LABELS = {
    "nueva": "Pregunta que el lector no leyó",
    "respuesta": "Respuesta correcta que el lector no leyó",
    "respuesta_distinta": "Respuesta correcta distinta",
    "tipo": "Tipo de pregunta distinto",
    "quitar": "No es una pregunta",
    "info": "Solo informativo",
}


def activity_key(filename: str) -> str:
    """Records and decisions are keyed by the activity file's name ("actividad6", "extra1")."""
    return os.path.splitext(os.path.basename(filename))[0]


# --- Decisions --------------------------------------------------------------

def _decisions_path(course_id) -> str:
    return os.path.join(PROJECT_ROOT, "workspace", str(course_id), DECISIONS_FILE)


def _load_all(course_id) -> dict:
    try:
        with open(_decisions_path(course_id), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def get_decisions(course_id, filename: str, html: str) -> dict:
    """{item id: "aceptar" | "descartar"} for this exact version of the activity."""
    entry = _load_all(course_id).get(activity_key(filename), {})
    return entry.get("decisiones", {}) if entry.get("html_hash") == shadow.html_hash(html) else {}


def set_decisions(course_id, filename: str, html: str, changes: dict) -> dict:
    """Applies {item id: decision or None} (None clears it) and returns the decisions now stored."""
    data = _load_all(course_id)
    key = activity_key(filename)
    current = get_decisions(course_id, filename, html)
    for item_id, decision in changes.items():
        if decision is None:
            current.pop(item_id, None)
        elif decision in DECISIONS:
            current[item_id] = decision
    data[key] = {"html_hash": shadow.html_hash(html), "decisiones": current}
    os.makedirs(os.path.dirname(_decisions_path(course_id)), exist_ok=True)
    with open(_decisions_path(course_id), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    return current


# --- The AI's reading as proposals ------------------------------------------

def load_record(course_id, filename: str, html: str):
    path = shadow.record_path(course_id, activity_key(filename), html)
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _final_attempts(record: dict) -> list:
    """The attempts whose answer the proposals come from (see ai_question_shadow._final)."""
    attempts = [a for a in record.get("intentos", []) if "ia" in a]
    level = record.get("nivel_final")
    if level == "pregunta":
        return [a for a in attempts if a["nivel"] == "pregunta"]
    for a in attempts:
        if a["nivel"] == level and a.get("clara"):
            return [a]
    return [attempts[-1]] if attempts else []


def _esc(text: str) -> str:
    return f"<p>{html_lib.escape(text or '')}</p>"


def _ai_preview(q: dict, numero=None) -> dict:
    """An AI question in the same shape as core.activity_preview.preview_questions, for the question card."""
    tipo = shadow.AI_TYPES.get(q.get("tipo"), "otra")
    options = [{"html": _esc(o["texto"]), "correcta": bool(o.get("correcta"))} for o in q.get("opciones", [])]
    return {"numero": numero, "tipo": tipo, "enunciado_html": _esc(q.get("enunciado")), "opciones": options,
            "correctas": sum(1 for o in options if o["correcta"]), "retroalimentacion": {},
            "origen_respuesta": q.get("origen_respuesta"), "evidencia": q.get("evidencia", "")}


def _parser_preview(p: dict, numero: int) -> dict:
    options = [{"html": _esc(o["texto"]), "correcta": o["correcta"]} for o in p["opciones"]]
    return {"numero": numero, "tipo": p["tipo"], "enunciado_html": _esc(p["enunciado"]), "opciones": options,
            "correctas": sum(1 for o in options if o["correcta"]), "retroalimentacion": {}}


def _drop_info_the_reader_now_covers(items: list, record: dict, html: str, course_id) -> list:
    """
    "Solo informativo" (the AI calls the question "otra": create it by hand)
    for a question the reader now uploads with a grade — e.g. a "(V)/(F)"
    statements group, read as one cloze question since the proposal was made —
    is wrong and has nothing to accept: left out. Only when the reading still
    has the same questions as the record.
    """
    current = shadow.parser_questions(html, course_id)
    if len(current) != len(record.get("parser", [])):
        return items

    def graded(q):
        return q["tipo"] != "description" and shadow._answer_problem(q) is None

    return [it for it in items
            if not (it["tipo"] == "info" and it["parser_indice"] is not None and graded(current[it["parser_indice"]]))]


def proposal_items(record: dict) -> list:
    """
    One item per thing the AI would change, from its verified answer only.
    Each item: id (stable for this record), tipo (KIND_LABELS), aceptable,
    nota, antes (parser question or None), despues (AI question or None), and
    what applying it needs (parser index, AI attempt/question index).
    """
    parsed = record["parser"]
    final_ids = {id(a) for a in _final_attempts(record)}
    items = []
    for a_index, attempt in enumerate(record.get("intentos", [])):
        if id(attempt) not in final_ids:
            continue
        # Parser indices this attempt was compared with.
        index_map = [attempt["pregunta"] - 1] if attempt["nivel"] == "pregunta" else list(range(len(parsed)))
        ai = attempt["ia"]
        comparison = attempt["comparacion"]
        whole_set = attempt["nivel"] != "pregunta"

        def item(kind, ia_i=None, parser_i=None, aceptable=True, nota=""):
            ident = f"{a_index}:{kind}:{ia_i if ia_i is not None else parser_i}"
            return {
                "id": ident, "tipo": kind, "etiqueta": KIND_LABELS[kind], "aceptable": aceptable, "nota": nota,
                "intento": a_index, "ia_indice": ia_i, "parser_indice": parser_i,
                "antes": _parser_preview(parsed[parser_i], parser_i + 1) if parser_i is not None else None,
                "despues": _ai_preview(ai[ia_i]) if ia_i is not None else None,
            }

        for m in comparison["emparejadas"]:
            q, p_i = ai[m["ia"]], index_map[m["parser"]]
            if not q["verificacion"]["valida"]:
                continue
            ai_type = shadow.AI_TYPES.get(q.get("tipo"))
            if ai_type is None:  # "otra": a kind of question the export can't build
                items.append(item("info", m["ia"], p_i, aceptable=False,
                                  nota="La IA indica que es un tipo de pregunta que no se puede subir "
                                       "automáticamente (por ejemplo, arrastrar sobre una imagen). Hay que crearla a mano en Moodle."))
            elif not m["mismo_tipo"] and ai_type == "essay":
                items.append(item("tipo", m["ia"], p_i,
                                  nota="Se subirá como pregunta abierta: el estudiante escribe y el docente califica a mano."))
            elif m["respuesta"] == "ia_completa" and not shadow._ai_unanswered(q):
                items.append(item("respuesta", m["ia"], p_i))
            elif m["respuesta"] == "distinta":
                items.append(item("respuesta_distinta", m["ia"], p_i,
                                  nota="El lector y la IA marcan respuestas distintas. Revísala con el documento antes de aceptar."))
        for ia_i in comparison["solo_ia"]:
            q = ai[ia_i]
            if not q["verificacion"]["valida"]:
                continue  # not verbatim in the document: never shown
            if shadow.AI_TYPES.get(q.get("tipo")) is None:
                items.append(item("info", ia_i, aceptable=False,
                                  nota="Tipo de pregunta que no se puede subir automáticamente. Hay que crearla a mano en Moodle."))
            elif shadow._ai_unanswered(q):
                items.append(item("nueva", ia_i, aceptable=False,
                                  nota="El documento no indica la respuesta correcta: complétala en el documento y vuelve a subirlo."))
            else:
                items.append(item("nueva", ia_i))
        if whole_set:
            for p in comparison["solo_parser"]:
                items.append(item("quitar", parser_i=index_map[p],
                                  nota="La IA no lo reconoce como pregunta (por ejemplo, una retroalimentación leída como pregunta)."))
    return items


def build_proposal(course_id, filename: str, html: str):
    """What the UI shows: the AI's reading as items, each with the user's decision. None if there's no reading."""
    record = load_record(course_id, filename, html)
    if record is None or "intentos" not in record or "error" in record:
        return None
    decisions = get_decisions(course_id, filename, html)
    items = _drop_info_the_reader_now_covers(proposal_items(record), record, html, course_id)
    for it in items:
        it["decision"] = decisions.get(it["id"])
    actionable = [it for it in items if it["aceptable"]]
    m = record.get("metricas", {})
    return {
        "nivel": record.get("nivel_final"),
        "preguntas_ia": m.get("ia", 0),
        "verificadas": m.get("ia_validas", 0),
        "items": items,
        "pendientes": sum(1 for it in actionable if not it["decision"]),
        "aceptadas": sum(1 for it in actionable if it["decision"] == "aceptar"),
        "completa": all(it["decision"] for it in actionable),
        "fecha": record.get("fecha"),
    }


# --- Applying accepted proposals --------------------------------------------

def _to_parser_question(q: dict) -> dict:
    """An AI question as a parsed question dict (actions.html_transformer.parse_questions shape)."""
    tipo = shadow.AI_TYPES.get(q.get("tipo"))
    question = {"stem_html": [_esc(q["enunciado"])], "options": [],
                "feedback": {"general": [], "correct": [], "incorrect": []}, "q_type": "multichoice", "origen": "ia"}
    if tipo == "verdadero_falso":
        correct = [o for o in q["opciones"] if o.get("correcta")]
        question["q_type"] = "truefalse"
        if correct:
            text = shadow._norm(correct[0]["texto"])
            question["tf_answer"] = text.startswith(("verdadero", "true", "v"))
    elif tipo in ("multichoice", "drag_drop"):
        question["q_type"] = tipo
        question["options"] = [{"html": _esc(o["texto"]), "is_correct": bool(o.get("correcta"))} for o in q["opciones"]]
    elif tipo == "cloze":
        question["q_type"] = "cloze"
    elif tipo == "essay":
        question["q_type"] = "essay"
    return question


def _apply_answer(question: dict, ai_q: dict) -> dict:
    """The parser's question with the AI's correct answer: marked on its own
    options when they are the same options as the AI's (keeps its formatting
    and feedback); otherwise — e.g. the parser swallowed the next question as
    extra options — the AI's version, with the parser's feedback."""
    from actions.html_transformer import _option_key
    tipo = shadow.AI_TYPES.get(ai_q.get("tipo"))
    if tipo == "verdadero_falso" and not question["options"]:
        converted = _to_parser_question(ai_q)
        question = dict(question, q_type="truefalse", tf_answer=converted.get("tf_answer"), origen="ia")
        return question
    correct = {_option_key(o["texto"]) for o in ai_q["opciones"] if o.get("correcta")}
    keys = [_option_key(BeautifulSoup(o["html"], "html.parser").get_text(" ")) for o in question["options"]]
    same_options = sorted(keys) == sorted(_option_key(o["texto"]) for o in ai_q["opciones"])
    if correct and same_options and all(keys.count(c) == 1 for c in correct):
        options = [dict(o, is_correct=k in correct) for o, k in zip(question["options"], keys)]
        return dict(question, options=options, origen="ia")
    replacement = _to_parser_question(ai_q)
    replacement["feedback"] = question["feedback"]
    return replacement


def final_questions(course_id, filename: str, html: str):
    """
    The questions to upload: the parser's, with every accepted proposal
    applied. None when nothing was accepted (callers then use the parser's
    reading as before).
    """
    from actions.html_transformer import parse_questions
    record = load_record(course_id, filename, html)
    decisions = get_decisions(course_id, filename, html)
    if record is None or not any(d == "aceptar" for d in decisions.values()):
        return None
    accepted = [it for it in proposal_items(record) if it["aceptable"] and decisions.get(it["id"]) == "aceptar"]
    if not accepted:
        return None

    parsed = parse_questions(html, course_id)
    if len(parsed) != len(record["parser"]):
        logger.warning(f"[IA] {filename}: la lectura cambió desde la propuesta; no se aplican sus cambios.")
        return None
    attempts = record["intentos"]
    removed, replaced, inserts = set(), {}, {}
    for it in accepted:
        ai_q = attempts[it["intento"]]["ia"][it["ia_indice"]] if it["ia_indice"] is not None else None
        if it["tipo"] == "quitar":
            removed.add(it["parser_indice"])
        elif it["tipo"] == "tipo":
            replaced[it["parser_indice"]] = dict(_to_parser_question(ai_q), feedback=parsed[it["parser_indice"]]["feedback"])
        elif it["tipo"] in ("respuesta", "respuesta_distinta"):
            replaced[it["parser_indice"]] = _apply_answer(parsed[it["parser_indice"]], ai_q)
        elif it["tipo"] == "nueva":
            # After the parser question paired with the closest earlier AI question.
            attempt = attempts[it["intento"]]
            index_map = [attempt["pregunta"] - 1] if attempt["nivel"] == "pregunta" else list(range(len(parsed)))
            pairs = {m["ia"]: index_map[m["parser"]] for m in attempt["comparacion"]["emparejadas"]}
            anchor = max((p for i, p in pairs.items() if i < it["ia_indice"]), default=-1)
            inserts.setdefault(anchor, []).append((it["ia_indice"], _to_parser_question(ai_q)))

    result = [q for _, q in sorted(inserts.get(-1, []), key=lambda x: x[0])]
    for i, q in enumerate(parsed):
        if i not in removed:
            result.append(replaced.get(i, q))
        result += [nq for _, nq in sorted(inserts.get(i, []), key=lambda x: x[0])]
    return result


def strip_accepted_questions(course_id, filename: str, original_html: str, description_html: str) -> str:
    """
    The quiz description without the questions the AI found and the parser
    didn't (the parser's own are already removed by strip_quiz_questions):
    every paragraph or list item whose text is one of those questions, its
    options or its answer line. Only verified questions, and not the ones the
    user discarded ("this isn't a question"): a question the user can't accept
    yet (no answer in the document) is still a question, and students must
    not see it in the description.
    """
    record = load_record(course_id, filename, original_html)
    decisions = get_decisions(course_id, filename, original_html)
    if record is None:
        return description_html
    texts = set()
    for it in proposal_items(record):
        # Questions only the AI found — including kinds that can't be uploaded.
        if it["tipo"] in ("nueva", "info") and it["parser_indice"] is None and decisions.get(it["id"]) != "descartar":
            q = record["intentos"][it["intento"]]["ia"][it["ia_indice"]]
            texts.add(_norm_line(q["enunciado"]))
            texts.update(_norm_line(o["texto"]) for o in q["opciones"])
            if q.get("evidencia"):
                texts.add(_norm_line(q["evidencia"]))
    if not texts:
        return description_html

    soup = BeautifulSoup(description_html, "html.parser")
    removed = 0
    for el in list(soup.find_all(["p", "li"])):
        if getattr(el, "decomposed", False) or el.parent is None:
            continue
        own = _norm_line(_own_text(el))
        if not own or not any(own == t or own.endswith(t) or (len(t) > 20 and t in own) for t in texts):
            continue
        # What follows a question and belongs to it: the explanation of its
        # answer, and a table it introduces (matching questions).
        anchor = el.parent if el.parent.name in ("ol", "ul") and el.find_next_sibling() is None else el
        follower = anchor.find_next_sibling()
        while follower is not None and _AFTER_QUESTION_RE.match(follower.get_text(" ").strip()):
            nxt = follower.find_next_sibling()
            follower.decompose()
            follower = nxt
        if follower is not None and follower.name == "table" and own.rstrip().endswith(":"):
            follower.decompose()
        el.decompose()
        removed += 1
    for lst in soup.find_all(["ul", "ol"]):
        if not lst.get_text(strip=True):
            lst.decompose()
    return str(soup) if removed else description_html


_AFTER_QUESTION_RE = re.compile(r"(?i)^(justificaci|retroalimentaci|explicaci|respuesta)")
_LABEL_RE = re.compile(r"^\s*(?:\([^)]{1,40}\)\s*)?(?:=?\s*(?:[a-eA-E][.)\-]|\d{1,2}[.)])\s*)?")


def _own_text(el) -> str:
    """The element's text without nested lists or tables (a list item's options are its own items)."""
    parts = []
    for node in el.find_all(string=True):
        cur, nested = node.parent, False
        while cur is not None and cur is not el:
            if cur.name in ("ol", "ul", "table"):
                nested = True
                break
            cur = cur.parent
        if not nested:
            parts.append(str(node))
    return " ".join(parts)


def _norm_line(text: str) -> str:
    """A line as the AI copies it: without a "(Opción múltiple)" label, number or option letter."""
    return shadow._norm(_LABEL_RE.sub("", text or ""))


def review_state(course_id, filename: str, html: str):
    """For the document review: None, or {"completa", "aceptadas", "pendientes"} of this activity's AI review."""
    proposal = build_proposal(course_id, filename, html)
    if proposal is None or not any(it["aceptable"] for it in proposal["items"]):
        return None
    return {k: proposal[k] for k in ("completa", "aceptadas", "pendientes")}
