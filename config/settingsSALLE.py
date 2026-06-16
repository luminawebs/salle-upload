import os
from dotenv import load_dotenv

# Load environment variables from a .env file if present
load_dotenv()


class ConfigSALLE:
    """Central configuration management for the LA SALLE project."""

    MOODLE_URL = os.getenv("MOODLE_URL", "https://moodle.example.com").rstrip("/")
    MOODLE_USERNAME = os.getenv("MOODLE_USERNAME")
    MOODLE_PASSWORD = os.getenv("MOODLE_PASSWORD")

    # Converts string values like "True", "1", "t" to a boolean
    HEADLESS_MODE = os.getenv("HEADLESS_MODE", "False").lower() in ("true", "1", "t")

    # Toggle specific processes

    # --------------------------------------------------- FASE 00 --------------------------------------------------------------------------------------------------------------------------------------------
    # Extrae el contenido de COURSEID.docx a un archivo HTML (assets/COURSEID/raw_docx_extracted.html) para validación.
    ENABLE_DOCX_PARSING = os.getenv("ENABLE_DOCX_PARSING", "True").lower() in (
        "true",
        "1",
        "t",
    )

    # Divide el archivo raw_docx_extracted.html en fragmentos HTML individuales (actividad1.html, Material_de_referencia_U1.html, etc.)
    ENABLE_DOCX_SPLITTING_HTML = os.getenv(
        "ENABLE_DOCX_SPLITTING_HTML", "True"
    ).lower() in (
        "true",
        "1",
        "t",
    )

    # --------------------------------------------------- FASE 01 --------------------------------------------------------------------------------------------------------------------------------------------

    ENABLE_UNIDADES_INTRO_SPLIT = os.getenv(
        "ENABLE_UNIDADES_INTRO_SPLIT", "False"
    ).lower() in (
        "true",
        "1",
        "t",
    )

    ENABLE_COURSE_STRUCTURE_CREATION = os.getenv(
        "ENABLE_COURSE_STRUCTURE_CREATION", "False"
    ).lower() in (
        "true",
        "1",
        "t",
    )

    # --------------------------------------------------- FASE 02 (Legacy Intros/Descriptions) --------------------------------------------------------------------------------------------------------------------------------------------

    # Sube las introducciones de las unidades a Moodle
    ENABLE_UNIDADES_INTRO_UPLOAD = os.getenv(
        "ENABLE_UNIDADES_INTRO_UPLOAD", "False"
    ).lower() in (
        "true",
        "1",
        "t",
    )

    # Sube los fragmentos HTML individuales a Moodle (actividad1.html, Material_de_referencia_U1.html, etc.)
    ENABLE_DOCX_UPLOAD_HTML = os.getenv("ENABLE_DOCX_UPLOAD_HTML", "False").lower() in (
        "true",
        "1",
        "t",
    )

    # Sube las rúbricas de calificación desde el DOCX
    ENABLE_DOCX_RUBRICA_UPLOAD = os.getenv(
        "ENABLE_DOCX_RUBRICA_UPLOAD", "False"
    ).lower() in (
        "true",
        "1",
        "t",
    )

    # Convierte preguntas de actividades (cuestionarios) a GIFT y las sube al Banco de Preguntas
    ENABLE_CUESTIONARIO_EXPORT = os.getenv(
        "ENABLE_CUESTIONARIO_EXPORT", "False"
    ).lower() in (
        "true",
        "1",
        "t",
    )

    # Actualiza la calificación máxima a 5.00 y distribuye el peso de las preguntas
    ENABLE_CUESTIONARIO_GRADE_UPDATE = os.getenv(
        "ENABLE_CUESTIONARIO_GRADE_UPDATE", "False"
    ).lower() in (
        "true",
        "1",
        "t",
    )

    # Cambia los nombres de las secciones del curso
    # ENABLE_SECTION_RENAME = os.getenv("ENABLE_SECTION_RENAME", "False").lower() in (
    #     "true",
    #     "1",
    #     "t",
    # )

    # Actualiza las condiciones de finalización de actividad a "Recibir una calificación" -> "Cualquier calificación"
    ENABLE_ACTIVITY_COMPLETION_UPDATE = os.getenv(
        "ENABLE_ACTIVITY_COMPLETION_UPDATE", "False"
    ).lower() in (
        "true",
        "1",
        "t",
    )

    # Depositphotos Credentials
    DEPOSITPHOTOS_USER = os.getenv("DEPOSITPHOTOS_USER", "maurizioroca@hotmail.com")
    DEPOSITPHOTOS_PASS = os.getenv("DEPOSITPHOTOS_PASS", "Ye:mW9&#hY&768z")

    # Global explicit wait timeout in seconds
    EXPLICIT_WAIT_TIME = 10

    # List of Moodle course IDs to iterate over
    COURSES_TO_PROCESS = [
        int(x.strip())
        for x in os.getenv("COURSES_TO_PROCESS", "10").split(",")
        if x.strip().isdigit()
    ]
