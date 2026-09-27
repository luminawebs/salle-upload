"""
Structured preview of one activity fragment for the review UI: its sections
("¿Qué vamos a lograr?", "¿Cómo lo vamos a lograr?", …) and, for quizzes, its
questions exactly as the Moodle export would read them — so what the user
checks in "Vista previa" is what gets uploaded, one question at a time.
"""
import re
import unicodedata

from bs4 import BeautifulSoup

# Section headings of an activity, matched accent-insensitively at the start
# of a block. Order here is only for matching; sections keep document order.
SECTION_LABELS = (
    ("QUE VAMOS A LOGRAR", "¿Qué vamos a lograr?"),
    ("COMO LO VAMOS A LOGRAR", "¿Cómo lo vamos a lograr?"),
    ("COMO LO VAMOS A EVALUAR", "¿Cómo lo vamos a evaluar?"),
    ("INFORMACION PARA EL EQUIPO DE PRODUCCION", "Información para el equipo de producción"),
    ("LECTURAS COMPLEMENTARIAS", "Lecturas y material"),
    ("LECTURAS BASICAS", "Lecturas y material"),
    ("LECTURAS PARA DESARROLLAR", "Lecturas y material"),
    ("MATERIAL DE REFERENCIA", "Lecturas y material"),
    ("MATERIAL DE ESTUDIO", "Lecturas y material"),
)
_INTRO_TITLE = "Presentación"


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.split()).upper().lstrip("¿¡ ")


def _label_for(text: str):
    norm = _norm(text)
    for key, title in SECTION_LABELS:
        if norm.startswith(key):
            # A block that is only the heading (plus punctuation) is a title;
            # a longer one also carries content and is kept in the section.
            only_heading = len(norm.rstrip("?:. ")) <= len(key) + 2
            return title, only_heading
    return None, False


def split_sections(html: str) -> list:
    """[{"titulo", "html"}] in document order; consecutive same-title sections are merged."""
    soup = BeautifulSoup(html, "html.parser")
    sections = []
    current = None
    for el in soup.contents:
        text = el.get_text(" ") if hasattr(el, "get_text") else str(el)
        if not text.strip() and not (hasattr(el, "find") and el.find(["img", "table"])):
            continue
        title, only_heading = _label_for(text) if len(text) < 400 else (None, False)
        if title:
            if current is None or current["titulo"] != title:
                current = {"titulo": title, "html": ""}
                sections.append(current)
            if not only_heading:
                current["html"] += str(el)
            continue
        if current is None:
            current = {"titulo": _INTRO_TITLE, "html": ""}
            sections.append(current)
        current["html"] += str(el)
    return [s for s in sections if s["html"].strip() or s["titulo"] != _INTRO_TITLE]


def build_preview(html: str, course_id=None) -> dict:
    """Sections plus, when the fragment has questions, each question as the export reads it."""
    from actions.html_transformer import parse_questions, summarize_quiz

    questions = []
    for number, q in enumerate(parse_questions(html, course_id), start=1):
        is_tf = q["q_type"] == "truefalse" and q.get("tf_answer") is not None
        options = [] if is_tf else [{"html": o["html"], "correcta": bool(o["is_correct"])} for o in q["options"]]
        if is_tf:
            options = [{"html": "Verdadero", "correcta": q["tf_answer"] is True},
                       {"html": "Falso", "correcta": q["tf_answer"] is False}]
        feedback = {k: "<br>".join(v) for k, v in q["feedback"].items() if v}
        questions.append({
            "numero": number,
            "tipo": "verdadero_falso" if is_tf else q["q_type"],
            "enunciado_html": "<br>".join(q["stem_html"]),
            "opciones": options,
            "correctas": sum(1 for o in options if o["correcta"]),
            "retroalimentacion": feedback,
        })

    summary = summarize_quiz(html, course_id) if questions or "respuesta correcta" in html.lower() else None

    # For a quiz: the description exactly as the upload cleans it (questions
    # and answers removed), so the user can check nothing leaks to students.
    from actions.html_transformer import remove_questions_from_html
    from core.data_parser import detect_activity_type
    activity_type = detect_activity_type(BeautifulSoup(html, "html.parser").get_text(" ").upper())
    description = remove_questions_from_html(html, is_quiz=True) if activity_type == "Cuestionario" else None

    return {
        "tipo": activity_type,
        "secciones": split_sections(html),
        "preguntas": questions,
        "resumen_preguntas": summary,
        "descripcion_moodle_html": description,
    }
