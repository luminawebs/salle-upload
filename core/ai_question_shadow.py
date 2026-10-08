"""
Shadow mode for the AI quiz-question reader.

When the document review finds a Cuestionario with gaps (questions it couldn't
read, or questions with no correct answer / no options), the AI reads the
smallest part of the document that can settle it, moving up only when the
answer isn't clear:
  1. "pregunta"  — just the question in doubt (when the parser knows which ones);
  2. "bloque"    — the whole set of questions (missing questions, or step 1 unclear);
  3. "actividad" — the whole activity, as a last resort.
Its answer is only *recorded*: nothing is shown in the UI and nothing is uploaded. The records in ai_shadow/ answer "how often
would the AI have been right?" before it's ever allowed near a real quiz.

"AI points, code cuts": the AI is asked to copy text verbatim, and every stem,
option and answer evidence it returns is checked against the document's own
text here. What fails that check is marked rejected in the record.

Turned on with AI_QUESTIONS_SHADOW=true (see config/settings.py). It refuses to
run without a spending cap. Measured offline with scripts/ai_shadow_eval.py.
"""
import difflib
import hashlib
import json
import logging
import os
import re
import threading
import time
import unicodedata

from bs4 import BeautifulSoup

from config.settings import Config
from core.question_types.catalog import ai_question_types, ai_type_guide

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHADOW_DIR = os.path.join(PROJECT_ROOT, "ai_shadow")
INTEGRATION = "quiz_shadow"
STEM_MATCH_RATIO = 0.8
# Leading list markers the AI may copy from a rendered list ("1.", "a)", "B.").
_ENUMERATOR_RE = re.compile(r'^\s*(?:\d{1,2}|[a-eA-E])\s*[.)-]\s+')

_lock = threading.Lock()

# Questions the parser flags one by one get one call each, up to this many;
# more than that goes straight to the whole block (one call instead of many).
MAX_QUESTION_CALLS = 3
LEVELS = ("pregunta", "bloque", "actividad")
AI_TYPES = ai_question_types()  # {ai type: parser tipo}, from the "Formatos de preguntas" catalog
CHOICE_TYPES = ("multichoice", "verdadero_falso", "truefalse")

PROMPT = """You read quiz questions from a university course document (Spanish).

{scope}

Rules:
- Copy all text VERBATIM from the document: same words, spelling, accents and punctuation. Do not fix typos, translate, summarize, complete or renumber anything.
- "enunciado": the question text only. Leave out its number ("1.", "Pregunta 3", "Enunciado:"). Keep gap markers such as [=Bogotá] or [[1]] exactly as written.
- "opciones": each answer option, verbatim, without its letter ("a)", "B.") or a leading "=". Empty list if the question has no options.
- "correcta" is true ONLY when the document itself shows it is the right answer. "origen_respuesta" says how:
  "linea_respuesta" (a line like "Respuesta correcta: ..."), "formato" (bold, underline, highlight, "=", "(respuesta correcta)" or another mark on the option),
  "clave" (an answer key elsewhere in the document), or "ninguna" (the document doesn't say — then no option is correct).
  NEVER use your own knowledge to choose an answer.
- "evidencia": for "linea_respuesta" or "clave", the exact document text that gives the answer; otherwise "".
- "tipo", one of (a question with no options that asks for a written answer is "abierta" even if the document doesn't say so;
  "opcion_multiple" also covers several correct options):
{types}
- Ignore instructions, objectives, rubrics and evaluation criteria: they are not questions.

HTML:
```html
{html}
```"""

SCOPES = {
    "pregunta": "This excerpt should contain ONE quiz question. Extract it (or every question, if it actually holds more than one).",
    "bloque": "This is the question section of a quiz. Extract EVERY question, in document order.",
    "actividad": "This is a whole quiz activity. Extract EVERY question of the quiz, in document order.",
}

SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "preguntas": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "enunciado": {"type": "STRING"},
                    "tipo": {"type": "STRING", "enum": [*AI_TYPES, "otra"]},
                    "opciones": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "texto": {"type": "STRING"},
                                "correcta": {"type": "BOOLEAN"},
                            },
                            "required": ["texto", "correcta"],
                        },
                    },
                    "origen_respuesta": {"type": "STRING", "enum": ["linea_respuesta", "formato", "clave", "ninguna"]},
                    "evidencia": {"type": "STRING"},
                },
                "required": ["enunciado", "tipo", "opciones", "origen_respuesta", "evidencia"],
            },
        },
    },
    "required": ["preguntas"],
}


def build_prompt(level: str, html: str) -> str:
    return (PROMPT.replace("{scope}", SCOPES[level]).replace("{types}", ai_type_guide())
            .replace("{html}", compact_html(html)))


# --- Text helpers -----------------------------------------------------------

def _norm(text: str) -> str:
    """Comparison form: NFC, one space, case-folded, typographic quotes/dashes unified."""
    text = unicodedata.normalize("NFC", text or "")
    text = text.translate(str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'", "–": "-", "—": "-", " ": " "}))
    return " ".join(text.split()).casefold()


def _plain(html: str) -> str:
    return " ".join(BeautifulSoup(html or "", "html.parser").get_text(" ").split())


def _found(text: str, source_norm: str) -> bool:
    """Verbatim (normalized) presence in the document; a leading list marker is tolerated."""
    t = _norm(text)
    if not t:
        return False
    if t in source_norm:
        return True
    stripped = _norm(_ENUMERATOR_RE.sub("", text))
    return bool(stripped) and stripped in source_norm


def compact_html(html: str) -> str:
    """The fragment without what costs tokens and says nothing about questions:
    style/class attributes and image data (an image stays as a placeholder)."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(True):
        if tag.name == "img":
            tag.attrs = {"alt": tag.get("alt", "imagen")}
        else:
            tag.attrs = {k: v for k, v in tag.attrs.items() if k in ("colspan", "rowspan")}
    return str(soup)


# --- What the parser reads today --------------------------------------------

def parser_questions(html: str, course_id=None) -> list:
    """The export's reading, as plain text: [{enunciado, tipo, opciones [{texto, correcta}]}]."""
    from core.activity_preview import preview_questions
    return [{
        "enunciado": _plain(q["enunciado_html"]),
        "tipo": q["tipo"],
        "opciones": [{"texto": _plain(o["html"]), "correcta": o["correcta"]} for o in q["opciones"]],
    } for q in preview_questions(html, course_id)]


def _answer_problem(q: dict):
    if q["tipo"] not in ("multichoice", "verdadero_falso", "truefalse"):
        return None
    if not q["opciones"]:
        return "sin_opciones"
    if not any(o["correcta"] for o in q["opciones"]):
        return "sin_correcta"
    return None


def find_gaps(html: str, course_id=None):
    """(gaps, parsed questions, quiz summary). gaps is empty when the parser read everything it evidently should."""
    from actions.html_transformer import summarize_quiz
    parsed = parser_questions(html, course_id)
    summary = summarize_quiz(html, course_id)
    gaps = []
    if summary["esperadas"] > summary["encontradas"]:
        gaps.append("faltan_preguntas")
    problems = {_answer_problem(q) for q in parsed} - {None}
    gaps += sorted(problems)
    return gaps, parsed, summary


# --- Verification and comparison (code, not AI) -----------------------------

def verify(ai_questions: list, html: str) -> list:
    """Adds "verificacion" to each AI question: is every piece of text really in the document?"""
    source_norm = _norm(_plain(html))
    for q in ai_questions:
        stem_ok = _found(q.get("enunciado", ""), source_norm)
        missing_options = [o["texto"] for o in q.get("opciones", []) if not _found(o["texto"], source_norm)]
        claims_answer = any(o.get("correcta") for o in q.get("opciones", []))
        origin = q.get("origen_respuesta", "ninguna")
        if not claims_answer:
            answer_ok = True
        elif origin in ("linea_respuesta", "clave"):
            answer_ok = _found(q.get("evidencia", ""), source_norm)
        elif origin == "formato":
            answer_ok = True  # can't be checked on plain text; counted separately
        else:
            answer_ok = False  # marked an answer while saying the document gives none
        q["verificacion"] = {
            "enunciado": stem_ok,
            "opciones_no_encontradas": missing_options,
            "respuesta": answer_ok,
            "valida": stem_ok and not missing_options and answer_ok,
        }
    return ai_questions


def _correct_set(q: dict) -> set:
    return {_norm(_ENUMERATOR_RE.sub("", o["texto"])) for o in q["opciones"] if o.get("correcta")}


def compare(parsed: list, ai_questions: list) -> dict:
    """Pairs each AI question with the parser's by stem similarity and says what differs."""
    def stem_key(q):
        return _norm(_ENUMERATOR_RE.sub("", q["enunciado"]))

    pairs, used = [], set()
    for ai_i, ai_q in enumerate(ai_questions):
        best, best_ratio = None, 0.0
        for p_i, p_q in enumerate(parsed):
            if p_i in used:
                continue
            a, b = stem_key(ai_q), stem_key(p_q)
            ratio = 1.0 if a and (a in b or b in a) else difflib.SequenceMatcher(None, a, b).ratio()
            if ratio > best_ratio:
                best, best_ratio = p_i, ratio
        if best is not None and best_ratio >= STEM_MATCH_RATIO:
            used.add(best)
            pairs.append((ai_i, best))

    matched = []
    for ai_i, p_i in pairs:
        ai_q, p_q = ai_questions[ai_i], parsed[p_i]
        parser_answer, ai_answer = _correct_set(p_q), _correct_set(ai_q)
        parser_type = "verdadero_falso" if p_q["tipo"] == "truefalse" else p_q["tipo"]
        matched.append({
            "ia": ai_i,
            "parser": p_i,
            "mismo_tipo": AI_TYPES.get(ai_q.get("tipo")) == parser_type,
            "mismas_opciones": len(ai_q["opciones"]) == len(p_q["opciones"]),
            "respuesta": ("igual" if parser_answer == ai_answer
                          else "ia_completa" if not parser_answer and ai_answer
                          else "ia_sin_respuesta" if parser_answer and not ai_answer
                          else "distinta"),
        })
    paired_ai = {a for a, _ in pairs}
    paired_parser = {p for _, p in pairs}
    return {
        "emparejadas": matched,
        "solo_ia": [i for i in range(len(ai_questions)) if i not in paired_ai],
        "solo_parser": [i for i in range(len(parsed)) if i not in paired_parser],
    }


def metrics(parsed: list, ai_questions: list, comparison: dict, summary: dict) -> dict:
    """The numbers the evaluation adds up across documents."""
    valid = [q["verificacion"]["valida"] for q in ai_questions]
    new = comparison["solo_ia"]
    new_valid = sum(1 for i in new if valid[i])
    filled = [m for m in comparison["emparejadas"] if m["respuesta"] == "ia_completa"]
    filled_valid = sum(1 for m in filled if valid[m["ia"]])
    return {
        "parser": len(parsed),
        "ia": len(ai_questions),
        "esperadas": summary["esperadas"],
        "ia_validas": sum(valid),
        "ia_rechazadas": len(valid) - sum(valid),
        "nuevas_validas": new_valid,
        "nuevas_rechazadas": len(new) - new_valid,
        "respuestas_completadas": filled_valid,
        "respuestas_distintas": sum(1 for m in comparison["emparejadas"] if m["respuesta"] == "distinta"),
        "solo_parser": len(comparison["solo_parser"]),
        "tipo_distinto": sum(1 for m in comparison["emparejadas"] if not m["mismo_tipo"]),
        "respuesta_por_formato": sum(1 for q in ai_questions if q.get("origen_respuesta") == "formato"
                                     and any(o.get("correcta") for o in q["opciones"])),
        # Would accepting the verified AI questions close the gap the review
        # reports? Parser items the AI didn't confirm don't count toward it.
        "cierra_brecha": len(comparison["emparejadas"]) + new_valid >= summary["esperadas"] and bool(new_valid or filled_valid),
    }


# --- Running ----------------------------------------------------------------

def shadow_ready() -> tuple:
    """(ok, reason). Shadow mode only runs with a spending cap it can actually enforce."""
    if not Config.AI_QUESTIONS_SHADOW:
        return False, "AI_QUESTIONS_SHADOW está desactivado."
    if Config.AI_BUDGET_USD <= 0 or Config.AI_COST_PER_1M_INPUT_TOKENS_USD <= 0 or Config.AI_COST_PER_1M_OUTPUT_TOKENS_USD <= 0:
        return False, ("Falta un tope de gasto: define AI_BUDGET_USD, AI_COST_PER_1M_INPUT_TOKENS_USD "
                       "y AI_COST_PER_1M_OUTPUT_TOKENS_USD (> 0) en .env.")
    if not os.environ.get("GEMINI_API_KEY"):
        return False, "Falta GEMINI_API_KEY en .env."
    return True, ""


def html_hash(html: str) -> str:
    return hashlib.sha256(html.encode("utf-8")).hexdigest()[:12]


def record_path(course_id, key: str, html: str) -> str:
    return os.path.join(SHADOW_DIR, str(course_id), f"{key}_{html_hash(html)}.json")


def _ai_unanswered(q: dict) -> bool:
    """An AI question that still has the problem: a choice question with no options or no answer."""
    return (AI_TYPES.get(q.get("tipo")) in CHOICE_TYPES
            and (not q["opciones"] or not any(o.get("correcta") for o in q["opciones"])))


def _attempt(client, level: str, excerpt: str, html: str, parsed: list, expected: int, course_id, key: str) -> dict:
    """
    One AI reading of `excerpt` (verified against the whole activity `html`),
    compared with the parser's questions for that same part. "clara" says the
    answer settles it: every AI question verified, none still unanswered, and
    as many questions as the document evidently has.
    """
    from core.ai_structurer import generate_json
    started = time.perf_counter()
    result = generate_json(client, build_prompt(level, excerpt), SCHEMA, INTEGRATION,
                           course_id=course_id, context=f"{key}:{level}")
    attempt = {"nivel": level, "segundos": round(time.perf_counter() - started, 2),
               "tokens": result.get("token_usage", {})}
    if "error" in result:
        attempt.update({"error": result["error"], "clara": False})
        return attempt
    ai_questions = verify(result.get("preguntas", []), html)
    comparison = compare(parsed, ai_questions)
    m = metrics(parsed, ai_questions, comparison, {"esperadas": expected})
    clear = (bool(ai_questions) and m["ia_rechazadas"] == 0
             and not any(_ai_unanswered(q) for q in ai_questions)
             and len(comparison["emparejadas"]) + m["nuevas_validas"] >= expected)
    attempt.update({"ia": ai_questions, "comparacion": comparison, "metricas": m, "clara": clear})
    return attempt


def _sum_metrics(attempts: list) -> dict:
    """Question-level attempts added up into one set of numbers for the record."""
    total = {}
    for a in attempts:
        for k, v in a.get("metricas", {}).items():
            if isinstance(v, bool):
                continue
            total[k] = total.get(k, 0) + v
    total["cierra_brecha"] = all(a.get("clara") for a in attempts)
    return total


def run_shadow(course_id, key: str, html: str, name: str = "", client=None, force: bool = False) -> dict:
    """
    Reads one quiz with the AI, escalating question → block → activity until
    the answer is clear, and saves the record. Returns it (or None when there's
    nothing to do: no gaps, already recorded for this exact text, or no
    client). `client` can be passed in (tests use a fake one).
    """
    path = record_path(course_id, key, html)
    if os.path.exists(path) and not force:
        return None
    gaps, parsed, summary = find_gaps(html, course_id)
    if not gaps and not force:
        return None

    from core.ai_structurer import get_gemini_client
    client = client or get_gemini_client(require_feature_flag=False)
    if client is None:
        return None

    from actions.html_transformer import question_excerpts
    excerpts, block = question_excerpts(html)
    attempts, final = [], None

    # 1. Only the questions the parser flags, when it knows which ones they are.
    flagged = [i for i, q in enumerate(parsed) if _answer_problem(q)]
    if flagged and "faltan_preguntas" not in gaps and len(flagged) <= MAX_QUESTION_CALLS             and len(excerpts) == len(parsed):
        level_attempts = []
        for i in flagged:
            a = _attempt(client, "pregunta", excerpts[i], html, [parsed[i]], 1, course_id, key)
            a["pregunta"] = i + 1
            level_attempts.append(a)
            if "error" in a:
                break
        attempts += level_attempts
        if all(a["clara"] for a in level_attempts):
            final = {"nivel": "pregunta", "metricas": _sum_metrics(level_attempts)}

    # 2. The whole set of questions. 3. The whole activity.
    for level, excerpt in (("bloque", block), ("actividad", html)):
        # A failed call (bad key, network, cut-off answer) isn't an unclear
        # answer: moving up a level would only repeat the failure.
        if final or not excerpt or (level == "actividad" and excerpt == block)                 or any("error" in a for a in attempts):
            continue
        a = _attempt(client, level, excerpt, html, parsed, summary["esperadas"], course_id, key)
        attempts.append(a)
        if a["clara"]:
            final = {"nivel": level, "metricas": a["metricas"]}
    if final is None and attempts and "metricas" in attempts[-1]:
        final = {"nivel": attempts[-1]["nivel"], "metricas": attempts[-1]["metricas"], "sin_resolver": True}

    record = {
        "fecha": time.strftime("%Y-%m-%d %H:%M:%S"),
        "curso": course_id,
        "actividad": key,
        "nombre": name,
        "html_hash": html_hash(html),
        "brechas": gaps,
        "resumen_parser": {k: summary[k] for k in ("encontradas", "declaradas", "esperadas")},
        "parser": parsed,
        "intentos": attempts,
        "tokens": {k: sum(a["tokens"].get(k, 0) or 0 for a in attempts) for k in ("input", "output")},
    }
    if final:
        record.update({"nivel_final": final["nivel"], "resuelta": not final.get("sin_resolver"),
                       "metricas": final["metricas"]})
    else:
        record["error"] = next((a["error"] for a in attempts if "error" in a), "La IA no devolvió respuesta.")

    # Saved only when the AI actually answered: a failed call must not mark
    # this text as "already recorded" and keep it from being retried.
    if any("error" not in a for a in attempts):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=1)
    logger.info(f"[IA sombra] {key}: " + (f"error: {record['error']}" if "error" in record else
                f"nivel {record['nivel_final']}, {'resuelta' if record['resuelta'] else 'sin resolver'}, "
                f"{len(attempts)} llamada(s)"))
    return record


def schedule_shadow(course_id, quizzes: list) -> None:
    """
    From the review: [(key, name, html)] of every Cuestionario. Runs in a
    background thread (one at a time) so the review never waits for the AI.
    Does nothing unless shadow mode is on and capped.
    """
    ok, reason = shadow_ready()
    if not ok:
        if Config.AI_QUESTIONS_SHADOW:
            logger.warning(f"[IA sombra] No se ejecuta: {reason}")
        return

    def work():
        with _lock:
            for key, name, html in quizzes:
                try:
                    run_shadow(course_id, key, html, name)
                except Exception as e:
                    logger.error(f"[IA sombra] {key}: {e}")

    threading.Thread(target=work, name="ai-question-shadow", daemon=True).start()
