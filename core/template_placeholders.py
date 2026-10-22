"""
Texts that only appear in a course design document when nobody filled in a
template section: "[nombre según plan de curso]", the sample question
"Enunciado Pregunta 1 / a. Opción 1"… The one place they are written down.

core/document_coverage.py uses them to report
- an unassigned block made of them as "Plantilla sin diligenciar" (not
  uploaded, never blocks), instead of "Contenido sin asignar";
- a recognized activity that still contains them (they'd be uploaded as is).

Only texts that prove the section is empty belong here. Template texts that
stay in well-filled documents too ("Indique si utilizará alguna____",
"Otra ¿Cuál?___", "(obligatorio solo en cursos de pregrado)") must not.
The "Formatos de preguntas" page lists them (/api/question-formats).
"""
import re
import unicodedata

# texto: as the template writes it (shown in the UI). patron: matched on the
# upper-cased, accent-free, single-spaced text (see _norm).
TEMPLATE_PLACEHOLDERS = [
    {
        "texto": "[nombre según plan de curso]",
        "patron": r"\[\s*NOMBRE SEGUN PLAN DE CURSO\s*\]",
        "donde": "Encabezado de la «Evaluación final»: va el nombre de la actividad.",
    },
    {
        "texto": "Ejemplo estructura de pregunta",
        "patron": r"EJEMPLO ESTRUCTURA DE PREGUNTA",
        "donde": "Título del ejemplo de preguntas de la «Evaluación final».",
    },
    {
        "texto": "Enunciado Pregunta 1",
        "patron": r"ENUNCIADO (DE LA )?PREGUNTA \d+",
        "donde": "Pregunta de ejemplo: va el enunciado real.",
    },
    {
        "texto": "a. Opción 1",
        "patron": r"(^|\s)[A-D][.)]\s*OPCION \d+\b",
        "donde": "Opciones de la pregunta de ejemplo.",
    },
    {
        "texto": "(incluir respuesta)",
        "patron": r"\(\s*INCLUIR RESPUESTA\s*\)",
        "donde": "Pregunta de completar de ejemplo: va la respuesta real.",
    },
]

_COMPILED = [(p, re.compile(p["patron"])) for p in TEMPLATE_PLACEHOLDERS]


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.split()).upper()


def find_placeholders(text: str) -> list:
    """The template texts (as written in the template) found in `text`."""
    norm = _norm(text)
    return [p["texto"] for p, rx in _COMPILED if rx.search(norm)]


def placeholder_catalog() -> list:
    """For the UI: each template text and where it comes from."""
    return [{"texto": p["texto"], "donde": p["donde"]} for p in TEMPLATE_PLACEHOLDERS]
