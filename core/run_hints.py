"""
Hints for errors we already know ("pistas"), added to the end-of-run summary.

Each entry matches the text of a logged error or warning and says, in Spanish, what
usually causes it and what to do; `codigo` points the developer to where it
happens (written only to the full run log, not to the user's summary).

Small on purpose: only failures seen in real runs. When a new one is
understood, add an entry here — tests/test_run_hints.py checks every entry
against a real example of its error message.
"""
import re

HINTS = (
    {
        "id": "curso_no_carga",
        "patron": r"could not load course|not a valid course view page",
        "ejemplo": "Could not load course 61980. Skipping all workflows for this course.",
        "pista": "No se pudo abrir el curso en Moodle. Revisa que el ID del curso sea correcto y que la "
                 "cuenta usada por la automatización esté matriculada en ese curso con permisos de edición.",
        "codigo": "actions/moodle_actions.py · navigate_to_course",
    },
    {
        "id": "modo_edicion",
        "patron": r"edit mode toggle|modo de edici[oó]n",
        "ejemplo": "Could not find any edit mode toggle or button ('interruptor de modo de edición').",
        "pista": "No se pudo activar el modo de edición: la cuenta necesita permisos de edición en el curso.",
        "codigo": "actions/section_actions.py · enable_edit_mode",
    },
    {
        "id": "disco_lleno",
        "patron": r"no space left on device",
        "ejemplo": "{'code': 65, 'message': 'No space left on device (os error 28)'}",
        "pista": "El servidor se quedó sin espacio en disco. Hay que liberar espacio (registros y cachés "
                 "antiguos) antes de volver a ejecutar.",
        "codigo": "Servidor: df -h; journalctl --vacuum-size; rm -rf /root/.cache/selenium",
    },
    {
        "id": "navegador",
        "patron": r"unable to obtain driver|chromedriver|session not created",
        "ejemplo": "Message: Unable to obtain driver for chrome",
        "pista": "No se pudo iniciar Chrome en el servidor. Suele deberse a falta de espacio en disco o a "
                 "una actualización de Chrome; el registro completo tiene el detalle.",
        "codigo": "core/driver_setup.py · get_driver",
    },
    {
        "id": "preguntas_cuestionario",
        "patron": r"'preguntas' tab|pregunta aleatoria|failed to add random questions",
        "ejemplo": "[ACTIVIDAD 4] Could not find visible 'una pregunta aleatoria' button.",
        "pista": "Las preguntas se importaron al banco, pero no se pudieron agregar al cuestionario. "
                 "En Moodle, abre el cuestionario y agrégalas desde el banco de preguntas.",
        "codigo": "actions/cuestionario_export_actions.py · add_questions_to_cuestionario",
    },
    {
        "id": "cuestionario_vacio",
        "patron": r"no hay ninguna pregunta para subir al cuestionario",
        "ejemplo": "ACTIVIDAD 1: no hay ninguna pregunta para subir al cuestionario.",
        "pista": "El cuestionario quedó sin preguntas. Abre la actividad en «Vista previa»: la pestaña "
                 "«Preguntas» muestra lo que se lee y «Revisión con IA» puede proponer las que faltan. "
                 "El formato esperado está en «Formatos de preguntas».",
        "codigo": "actions/cuestionario_export_actions.py · export_quiz_questions",
    },
    {
        "id": "importar_preguntas",
        "patron": r"failed to import moodle xml",
        "ejemplo": "Failed to import Moodle XML file for ACTIVIDAD 4: timeout",
        "pista": "No se pudieron importar las preguntas del cuestionario. Revisa en «Vista previa» que las "
                 "preguntas se lean bien y vuelve a ejecutar solo ese paso desde «Configuración avanzada».",
        "codigo": "actions/cuestionario_export_actions.py · import_xml_to_cuestionario",
    },
    {
        "id": "rubrica",
        "patron": r"could not find moodle assignment|rubric editor",
        "ejemplo": "Could not find Moodle assignment for ACTIVIDAD 2. Skipping rubric.",
        "pista": "No se pudo subir una rúbrica: la tarea no se encontró en el curso por su nombre. "
                 "Revisa que en Moodle su nombre empiece por «ACTIVIDAD N».",
        "codigo": "actions/docx_rubrica_actions.py · _upload_rubric",
    },
    {
        "id": "actividad_no_encontrada",
        "patron": r"could not extract edit url for|failed to extract edit url",
        "ejemplo": "Could not extract edit URL for ACTIVIDAD 3.",
        "pista": "No se encontró una actividad en el curso por su nombre, así que no se actualizó. Revisa "
                 "que exista en Moodle y que su nombre empiece como en el documento («ACTIVIDAD N…»).",
        "codigo": "actions/docx_upload_actions.py · get_edit_url_for_activity",
    },
    {
        "id": "tiempo_agotado",
        "patron": r"timed out|timeoutexception|renderer",
        "ejemplo": "TimeoutException: Message: timeout: Timed out receiving message from renderer",
        "pista": "Moodle tardó demasiado en responder. Suele ser lentitud momentánea; vuelve a ejecutar "
                 "solo el paso que falló desde «Configuración avanzada».",
        "codigo": "core/driver_setup.py (page load timeout 90 s) · el paso indicado en el error",
    },
)

_COMPILED = [(hint, re.compile(hint["patron"], re.IGNORECASE)) for hint in HINTS]


def hints_for(messages) -> list:
    """The hints matching any of these error messages, each once, in catalog order."""
    found = []
    for hint, pattern in _COMPILED:
        if any(pattern.search(m or "") for m in messages):
            found.append(hint)
    return found
