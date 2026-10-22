"""
A suggested type for an activity whose author marked no tool with an X in
"Herramientas de la plataforma virtual": what its own text asks the student
to do. Only a suggestion, shown in the review panel; the user confirms it
(core/document_corrections.py, "tipos") before it changes the upload.

The tools table itself is left out: it always names Foro, Tarea and
Cuestionario, marked or not.
"""
import re
import unicodedata

# (type, strong?, pattern on the upper-cased accent-free text, reason shown).
# Strong clues say what the student does in the activity; weak ones (the
# product is a file, there's a rubric) also show up in forums and quizzes,
# so they only count when no strong clue does.
_CLUES = [
    ("Cuestionario", True, r"\(\s*RESPUESTA( CORRECTA)?\s*\)|RESPUESTA CORRECTA\s*:", "tiene preguntas con su respuesta marcada"),
    ("Cuestionario", True, r"\bCUESTIONARIO\b|\bINTENTO\b|SELECCION MULTIPLE|VERDADERO O FALSO|\bPREGUNTA 1\b",
     "habla de un cuestionario en línea (preguntas, intento, selección múltiple…)"),
    ("Foro", True, r"\bFORO\b|\bDEBAT\w*", "pide participar en un foro o debate"),
    ("Foro", True, r"\b(RESPONDE|COMENTA|RETROALIMENTA|REPLICA)\w*( \w+){0,3} (DOS|TRES|AL MENOS \w+|UN|OTROS?|TUS|SUS) COMPANER",
     "pide responder a compañeros"),
    ("Foro", True, r"\bPUBLICA\w* (TU|SU) (APORTE|INTERVENCION|PARTICIPACION)\b", "pide publicar un aporte"),
    ("Tarea", True, r"\b(ENTREGA|ENTREGAR|SUBE|SUBIR|ADJUNTA|ADJUNTAR|ENVIA|ENVIAR)\b", "pide entregar o subir un archivo"),
    ("Tarea", False, r"\b(VIDEO|DOCUMENTO|INFORME|ENSAYO|INFOGRAFIA|PODCAST|MAPA (MENTAL|CONCEPTUAL)|POSTER|PRODUCTO)\b",
     "el producto parece un archivo (video, documento, informe…)"),
    ("Tarea", False, r"CRITERIOS DE DESEMPENO", "tiene una rúbrica de evaluación"),
]
_COMPILED = [(t, strong, re.compile(p), why) for t, strong, p, why in _CLUES]

# Mentions that name no activity type: the course's permanent Q&A forum.
_NOISE_RE = re.compile(r"FORO (PERMANENTE )?DE DUDAS|FORO DE AVISOS")

# From the tools row to the end of its list ("… Otra ¿Cuál?____").
_TOOLS_ROW_RE = re.compile(
    r"(ELIJA LA )?HERRAMIENTAS? DE LA PLATAFORMA VIRTUAL.*?(OTRA\W*CUAL\W*_*|$)", re.DOTALL)
_EXTERNAL_TOOLS_RE = re.compile(r"HERRAMIENTAS WEB EXTERNAS A LA PLATAFORMA.*?(INDIQUE SI UTILIZARA ALGUNA_*|$)", re.DOTALL)


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.split()).upper()


def suggest_activity_type(text: str):
    """
    {"tipo": "Tarea", "razones": ["pide entregar…", …]} when the clues point
    to one type, or None when there are none or they point to several
    (the user then chooses without a suggestion).
    """
    norm = _EXTERNAL_TOOLS_RE.sub(" ", _TOOLS_ROW_RE.sub(" ", _norm(text)))
    norm = _NOISE_RE.sub(" ", norm)
    strong, weak = {}, {}
    for tipo, is_strong, rx, why in _COMPILED:
        if rx.search(norm):
            (strong if is_strong else weak).setdefault(tipo, []).append(why)
    reasons = strong or weak
    if not reasons:
        return None
    # A quiz's own questions settle it; otherwise the type with the most
    # distinct clues wins, and a tie is no suggestion.
    if _CLUES[0][3] in strong.get("Cuestionario", []):
        return {"tipo": "Cuestionario", "razones": strong["Cuestionario"]}
    ranked = sorted(reasons.items(), key=lambda kv: len(kv[1]), reverse=True)
    if len(ranked) > 1 and len(ranked[0][1]) == len(ranked[1][1]):
        return None
    tipo = ranked[0][0]
    return {"tipo": tipo, "razones": reasons[tipo] + (weak.get(tipo, []) if reasons is strong else [])}
