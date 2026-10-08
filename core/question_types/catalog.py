"""
The question formats the quiz export understands, with an example of each
exactly as a teacher writes it in the .docx.

This is the one source for the "Formatos de preguntas" guide in the UI and for
the question types the AI is told about (core/ai_question_shadow.py). The guide
never shows a hand-written result: render_catalog() runs every example through
the real parser and the real Moodle XML builders, and
tests/test_question_formats.py fails if an example stops being read as its
type. So when the parser changes, the guide shows the change, or a test says
the example (or the parser) needs fixing.
"""
import html as html_lib

# "tipo" is what the preview reports (core/activity_preview.preview_questions);
# "correctas" is how many options each example marks as correct. The first
# variant of each format is the course template ("Pregunta N / Tipo / Enunciado
# / Opciones"), as in DP. Lenguaje de programación I (QUESTION_EDIT).
QUESTION_FORMATS = [
    {
        "id": "opcion_multiple",
        "nombre": "Opción múltiple (una respuesta)",
        "moodle": "multichoice",
        "descripcion": "Una pregunta con varias opciones y una sola correcta. "
                       "La respuesta correcta se puede indicar de tres formas.",
        "variantes": [
            {"titulo": "Plantilla recomendada", "tipo": "multichoice", "correctas": 1, "lineas": [
                "Pregunta 1",
                "Tipo: multiple",
                "Enunciado: ¿En qué año comenzó la Segunda Guerra Mundial?",
                "Opciones:",
                "=1939",
                "1940",
                "1938",
                "Retroalimentación correcta: ¡Correcto! Comenzó el 1 de septiembre de 1939.",
                "Retroalimentación incorrecta: La respuesta correcta es 1939.",
            ]},
            {"titulo": "Con una línea «Respuesta correcta»", "tipo": "multichoice", "correctas": 1, "lineas": [
                "1. ¿Cuál es la capital de Colombia?",
                "A. Medellín",
                "B. Bogotá",
                "C. Cali",
                "Respuesta correcta: Bogotá",
                "Retroalimentación: Bogotá es la capital desde 1538.",
            ]},
            {"titulo": "Marcando la opción con «(respuesta correcta)»", "tipo": "multichoice", "correctas": 1, "lineas": [
                "2. ¿Cuál es el río más largo de Colombia?",
                "a) Río Cauca",
                "b) Río Magdalena (respuesta correcta)",
                "c) Río Atrato",
            ]},
            {"titulo": "Con «=» delante de la opción correcta", "tipo": "multichoice", "correctas": 1, "lineas": [
                "3. ¿En qué año se fundó Bogotá?",
                "a) 1492",
                "=b) 1538",
                "c) 1810",
            ]},
        ],
        "notas": [
            "Las opciones empiezan con una letra: «A.», «a)» o «b.».",
            "La línea «Respuesta correcta:» debe repetir el texto de una opción (con o sin su letra).",
        ],
    },
    {
        "id": "opcion_multiple_varias",
        "nombre": "Opción múltiple (varias respuestas)",
        "moodle": "multichoice",
        "descripcion": "Igual que la anterior, pero con más de una opción correcta. "
                       "El puntaje se reparte entre las opciones correctas.",
        "variantes": [
            {"titulo": "Plantilla recomendada", "tipo": "multichoice", "correctas": 2, "lineas": [
                "Pregunta 1",
                "Tipo: multiple",
                "Enunciado: ¿Cuáles de los siguientes son gases nobles?",
                "Opciones:",
                "=Helio",
                "=Neón",
                "Oxígeno",
            ]},
            {"titulo": "Marcando cada opción correcta", "tipo": "multichoice", "correctas": 2, "lineas": [
                "1. ¿Cuáles de estos son lenguajes de programación?",
                "a) Python (respuesta correcta)",
                "b) HTML",
                "c) Java (respuesta correcta)",
            ]},
        ],
        "notas": ["También sirve «=» delante de cada opción correcta."],
    },
    {
        "id": "verdadero_falso",
        "nombre": "Verdadero o falso",
        "moodle": "truefalse",
        "descripcion": "Una afirmación que el estudiante marca como verdadera o falsa.",
        "variantes": [
            {"titulo": "Plantilla recomendada", "tipo": "verdadero_falso", "correctas": 1, "lineas": [
                "Pregunta 1",
                "Tipo: verdadero_falso",
                "Enunciado: La Antártida es el continente más grande del mundo.",
                "Opciones:",
                "Verdadero",
                "=Falso",
                "Retroalimentación correcta: ¡Correcto! El continente más grande es Asia.",
            ]},
            {"titulo": "Afirmación y «Respuesta correcta»", "tipo": "verdadero_falso", "correctas": 1, "lineas": [
                "1. El agua hierve a 100 °C al nivel del mar.",
                "Respuesta correcta: Verdadero",
            ]},
            {"titulo": "Con las opciones Verdadero y Falso", "tipo": "verdadero_falso", "correctas": 1, "lineas": [
                "2. La Tierra es plana.",
                "a) Verdadero",
                "b) Falso (respuesta correcta)",
            ]},
        ],
        "notas": ["La respuesta se escribe «Verdadero» o «Falso»."],
    },
    {
        "id": "completar",
        "nombre": "Completar espacios",
        "moodle": "cloze",
        "descripcion": "Un texto con espacios en blanco. Cada respuesta va entre corchetes, con «=» delante.",
        "variantes": [
            {"titulo": "Plantilla recomendada", "tipo": "cloze", "correctas": 0, "lineas": [
                "Pregunta 1",
                "Tipo: completar",
                "Enunciado: El río más largo del mundo es el [=Amazonas] y el segundo es el [=Nilo].",
                "Retroalimentación correcta: ¡Excelente!",
            ]},
            {"titulo": "Respuestas entre corchetes", "tipo": "cloze", "correctas": 0, "lineas": [
                "1. La capital de Colombia es [=Bogotá] y la de Perú es [=Lima].",
            ]},
        ],
        "notas": ["El estudiante escribe la respuesta; debe coincidir con el texto entre corchetes."],
    },
    {
        "id": "arrastrar_soltar",
        "nombre": "Arrastrar y soltar",
        "moodle": "ddwtos",
        "descripcion": "Un texto con espacios numerados [[1]], [[2]]… y, debajo, la lista de palabras para "
                       "arrastrar. La palabra 1 va en [[1]], la 2 en [[2]]; las demás sobran (distractores).",
        "variantes": [
            {"titulo": "Plantilla recomendada", "tipo": "drag_drop", "correctas": 2, "lineas": [
                "Pregunta 1",
                "Tipo: arrastrar_soltar",
                "Enunciado: En la fotosíntesis, las plantas toman [[1]] y producen [[2]].",
                "Opciones:",
                "=Dióxido de carbono",
                "=Glucosa",
                "Plutón",
            ]},
            {"titulo": "Espacios numerados y opciones", "tipo": "drag_drop", "correctas": 0, "lineas": [
                "1. [[1]] es un lenguaje de programación y [[2]] es una base de datos.",
                "Opciones:",
                "Python",
                "PostgreSQL",
                "Excel",
            ]},
        ],
        "notas": ["La línea «Opciones:» es obligatoria antes de la lista de palabras."],
    },
    {
        "id": "abierta",
        "nombre": "Pregunta abierta",
        "moodle": "essay",
        "descripcion": "El estudiante responde con sus palabras y el docente califica a mano. "
                       "Se indica con la línea «Tipo: abierta».",
        "variantes": [
            {"titulo": "Plantilla recomendada", "tipo": "essay", "correctas": 0, "lineas": [
                "Pregunta 1",
                "Tipo: abierta",
                "Enunciado: Explique con sus palabras qué es la restitución de tierras.",
                "Retroalimentación correcta: Debe mencionar la fase administrativa y la judicial.",
            ]},
            {"titulo": "Con «Tipo: abierta»", "tipo": "essay", "correctas": 0, "lineas": [
                "1. Explique con sus palabras qué es la restitución de tierras.",
                "Tipo: abierta",
                "Retroalimentación para respuesta correcta: Debe mencionar la fase administrativa y la judicial.",
            ]},
        ],
        "notas": [
            "Sin «Tipo: abierta», una pregunta sin opciones se sube como texto, no como pregunta.",
            "La retroalimentación le llega al docente como guía para calificar.",
        ],
    },
]

GENERAL_RULES = [
    "Numere cada pregunta: «1.», «2.»… o «Pregunta 1».",
    "La retroalimentación es opcional: «Retroalimentación:» (para todos), "
    "«Retroalimentación para respuesta correcta:» o «… para respuestas incorrectas:».",
    "Las preguntas terminan donde empieza «¿Cómo lo vamos a evaluar?», «Entregable» "
    "o «Información para el equipo de producción».",
]


def example_html(lines: list) -> str:
    return "".join(f"<p>{html_lib.escape(line)}</p>" for line in lines)


def render_catalog() -> dict:
    """Every format with each example as the export reads it (preview + Moodle XML), computed now."""
    from actions.html_transformer import parse_questions, question_handler
    from core.activity_preview import preview_questions

    formats = []
    for fmt in QUESTION_FORMATS:
        variants = []
        for variant in fmt["variantes"]:
            html = example_html(variant["lineas"])
            parsed = parse_questions(html)
            xml = "\n".join(question_handler(q, n)[0].to_moodle_xml() for n, q in enumerate(parsed, start=1))
            variants.append({**variant, "preguntas": preview_questions(html), "xml": xml})
        formats.append({**fmt, "variantes": variants})
    return {"formatos": formats, "reglas": GENERAL_RULES}


def ai_question_types() -> dict:
    """
    The question types the AI may report, from the formats above: {ai_type: parser tipo}.
    Formats that the export treats as the same type (one or several correct
    options) are one AI type. "otra" is anything the export doesn't support.
    """
    types, seen = {}, set()
    for fmt in QUESTION_FORMATS:
        tipo = fmt["variantes"][0]["tipo"]
        if tipo not in seen:
            seen.add(tipo)
            types[fmt["id"]] = tipo
    return types


def ai_type_guide() -> str:
    """One line per AI type for the prompt, from each format's own description."""
    names = {fmt["id"]: fmt for fmt in QUESTION_FORMATS}
    lines = [f'  "{key}": {names[key]["nombre"]}. {names[key]["descripcion"]}' for key in ai_question_types()]
    lines.append('  "otra": any other kind (e.g. drag onto an image, matching).')
    return "\n".join(lines)
