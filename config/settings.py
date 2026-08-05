import os
from dotenv import load_dotenv

# Load environment variables from a .env file if present
load_dotenv()


class Config:
    """Central configuration management for the project. Includes both active and legacy settings."""

    # ==================================================================================================
    # --------------------------------- ACTIVE SETTINGS ------------------------------------------------
    # ==================================================================================================
    ENABLE_AI_FEATURES = os.getenv("ENABLE_AI_FEATURES", "True").lower() in ("true", "1", "t")
    TESTING_MODE = os.getenv("TESTING_MODE", "False").lower() in ("true", "1", "t")

    
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    WORKSPACE_DIR = os.path.join(BASE_DIR, "workspace")

    USE_TESTING_ENV = os.getenv("USE_TESTING_ENV", "False").lower() in ("true", "1", "t")

    if USE_TESTING_ENV:
        MOODLE_URL = os.getenv("MOODLE_TESTING_URL", "https://testing.moodle.example.com").rstrip("/")
    else:
        MOODLE_URL = os.getenv("MOODLE_URL", "https://moodle.example.com").rstrip("/")
        
    MOODLE_USERNAME = os.getenv("MOODLE_USERNAME")
    MOODLE_PASSWORD = os.getenv("MOODLE_PASSWORD")

    # Converts string values like "True", "1", "t" to a boolean
    HEADLESS_MODE = os.getenv("HEADLESS_MODE", "False").lower() in ("true", "1", "t")

    # Toggle specific processes

    # --------------------------------------------------- FASE 00 --------------------------------------------------------------------------------------------------------------------------------------------
    # Extrae el contenido de COURSEID.docx a un archivo HTML (workspace/COURSEID/raw_docx_extracted.html) para validación.
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
        "ENABLE_UNIDADES_INTRO_SPLIT", "True"
    ).lower() in (
        "true",
        "1",
        "t",
    )

    ENABLE_COURSE_FORMAT_CHANGE = os.getenv(
        "ENABLE_COURSE_FORMAT_CHANGE", "True"
    ).lower() in (
        "true",
        "1",
        "t",
    )

    ENABLE_COURSE_STRUCTURE_CREATION = os.getenv(
        "ENABLE_COURSE_STRUCTURE_CREATION", "True"
    ).lower() in (
        "true",
        "1",
        "t",
    )

    # --------------------------------------------------- FASE 02 (Legacy Intros/Descriptions) --------------------------------------------------------------------------------------------------------------------------------------------

    # Sube las introducciones de las unidades a Moodle
    ENABLE_UNIDADES_INTRO_UPLOAD = os.getenv(
        "ENABLE_UNIDADES_INTRO_UPLOAD", "True"
    ).lower() in (
        "true",
        "1",
        "t",
    )

    # Sube los fragmentos HTML individuales a Moodle (actividad1.html, Material_de_referencia_U1.html, etc.)
    ENABLE_DOCX_UPLOAD_HTML = os.getenv("ENABLE_DOCX_UPLOAD_HTML", "True").lower() in (
        "true",
        "1",
        "t",
    )

    # Sube las rúbricas de calificación desde el DOCX
    ENABLE_DOCX_RUBRICA_UPLOAD = os.getenv(
        "ENABLE_DOCX_RUBRICA_UPLOAD", "True"
    ).lower() in (
        "true",
        "1",
        "t",
    )

    ENABLE_CUESTIONARIO_EXPORT = os.getenv(
        "ENABLE_CUESTIONARIO_EXPORT", "True"
    ).lower() in (
        "true",
        "1",
        "t",
    )

    # Añadir recursos finales a las unidades (Materiales de estudio y Página)
    ENABLE_MATERIALES_ESTUDIO_EXPORT = os.getenv(
        "ENABLE_MATERIALES_ESTUDIO_EXPORT", "True"
    ).lower() in (
        "true",
        "1",
        "t",
    )

    # Actualiza la calificación máxima a 5.00 y distribuye el peso de las preguntas
    ENABLE_CUESTIONARIO_GRADE_UPDATE = os.getenv(
        "ENABLE_CUESTIONARIO_GRADE_UPDATE", "True"
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
        "ENABLE_ACTIVITY_COMPLETION_UPDATE", "True"
    ).lower() in (
        "true",
        "1",
        "t",
    )
    
    ENABLE_FINAL_COURSE_FORMAT_BUTTONS = os.getenv(
        "ENABLE_FINAL_COURSE_FORMAT_BUTTONS", "True"
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

    # ==================================================================================================
    # -------------------------------- INACTIVE / LEGACY SETTINGS --------------------------------------
    # ==================================================================================================



    # Converts string values like "True", "1", "t" to a boolean

    # Remote Execution Toggle
    EXECUTE_REMOTE = os.getenv("EXECUTE_REMOTE", "False").lower() in ("true", "1", "t")
    SELENIUM_REMOTE_URL = os.getenv("SELENIUM_REMOTE_URL", "http://localhost:4444/wd/hub")

    # Custom paths for Chrome/Chromedriver (useful for Linux servers with architecture issues)
    CHROME_BINARY_LOCATION = os.getenv("CHROME_BINARY_LOCATION")
    CHROMEDRIVER_PATH = os.getenv("CHROMEDRIVER_PATH")

    # Toggle specific processes

    # --------------------------------------------------- FASE 00 --------------------------------------------------------------------------------------------------------------------------------------------
    # Extrae el contenido de 8.docx a un archivo HTML (workspace/COURSEID/raw_docx_extracted.html) para validación.

    # Divide el archivo raw_docx_extracted.html en fragmentos HTML individuales (actividad1.html, Material_de_referencia_U1.html, etc.)

    # --------------------------------------------------- FASE 01 --------------------------------------------------------------------------------------------------------------------------------------------
    # Cambia los nombres de las secciones del curso
    ENABLE_SECTION_RENAME = os.getenv("ENABLE_SECTION_RENAME", "False").lower() in ("true", "1", "yes")
    # Actualiza la descripción de las secciones
    # descargar propuesta metodologica, pasar a drive (limpiar), descargar como .csv
    # loads week-by-week summaries from 'workspace/COURSEID/contenidos.json'.
    ENABLE_SECTION_DESCRIPTION_UPDATE = os.getenv("ENABLE_SECTION_DESCRIPTION_UPDATE", "False").lower() in ("true", "1", "yes")

    # Genera los archivos HTML locales de introducción (semana_introduccion_XX.html) extraídos de Moodle -> archivo: introduccion_actions.py (week:son/off)
    ENABLE_GENERATE_HTML_INTRO = os.getenv("ENABLE_GENERATE_HTML_INTRO", "False").lower() in ("true", "1", "yes")

    # Genera el archivo HTML de introducción general (introduccion_general.html) extraído de Moodle -> archivo: introduccion_general_actions.py
    # el nombre del curso va en negrilla.
    ENABLE_GENERATE_HTML_INTRO_GENERAL = os.getenv("ENABLE_GENERATE_HTML_INTRO_GENERAL", "False").lower() in ("true", "1", "yes")

    # --------------------------------------------------- FASE 02 --------------------------------------------------------------------------------------------------------------------------------------------------
    # Importa info de las infografías !!!!!!!!!!!!!!!!!!!!!!! AGREGAR NOMBRE DEL CURSO en el .json
    ENABLE_INFOGRAFIA_EXPORT = os.getenv("ENABLE_INFOGRAFIA_EXPORT", "False").lower() in ("true", "1", "yes")
    # Descarga fotos de depositphotos
    ENABLE_DEPOSITPHOTOS_DOWNLOAD = os.getenv("ENABLE_DEPOSITPHOTOS_DOWNLOAD", "False").lower() in ("true", "1", "yes")
    # Exporta contenido de Foros
    # aqui es necesario añadir italicas bien, revisar si está bien linkeado con el glosario.

    ENABLE_FORO_EXPORT = os.getenv("ENABLE_FORO_EXPORT", "False").lower() in ("true", "1", "yes")
    # Exporta recursos de actualidad
    ENABLE_ACTUALIDAD_EXPORT = os.getenv("ENABLE_ACTUALIDAD_EXPORT", "False").lower() in ("true", "1", "yes")
    # Exporta contenido de Preguntas (Afianzamiento/Examen) (SIN ERRORES DE EJECUCION)
    ENABLE_PREGUNTAS_EXPORT = os.getenv("ENABLE_PREGUNTAS_EXPORT", "False").lower() in ("true", "1", "yes")
    # Sube recursos de apoyo/actualidad al glosario
    ENABLE_RECURSOS_APOYO_EXPORT = os.getenv("ENABLE_RECURSOS_APOYO_EXPORT", "False").lower() in ("true", "1", "yes")

    # Reemplaza clase txt-blue por txt-v-blue en definiciones also, it removes "R1:" "R2:", ads missing urls, removes ending ":" from titles -> OPTIONAL
    ENABLE_RECURSOS_APOYO_EDIT_CLASSES = os.getenv("ENABLE_RECURSOS_APOYO_EDIT_CLASSES", "False").lower() in ("true", "1", "yes")

    # ------------------------------------------------------- FASE 03 ACTIVIDADES -----------------------------------------------------------------------------------------------------------------------------------------
    # Exporta y sube actividades (talleres S2, S4, S6, S8) a Moodle
    # PLantilla_Taller_S*.docx
    ENABLE_ACTIVIDAD_EXPORT = os.getenv("ENABLE_ACTIVIDAD_EXPORT", "False").lower() in ("true", "1", "yes")

    # Sube los recursos bibliográficos de las actividades al glosario
    ENABLE_ACTIVIDAD_RECURSOS_EXPORT = os.getenv("ENABLE_ACTIVIDAD_RECURSOS_EXPORT", "False").lower() in ("true", "1", "yes")

    # Rellena la rúbrica de calificación avanzada en cada actividad S2/S4/S6/S8
    ENABLE_ACTIVIDAD_RUBRICA_EXPORT = os.getenv("ENABLE_ACTIVIDAD_RUBRICA_EXPORT", "False").lower() in ("true", "1", "yes")

    # Exporta y sube trabajos finales (S3, S6, S8) a Moodle
    # Fuente: workspace/COURSEID/actividades-trabajo-final/SX_Trabajo.html
    # Destino: actividad Moodle "SX | Trabajo"
    ENABLE_TRABAJO_EXPORT = os.getenv("ENABLE_TRABAJO_EXPORT", "False").lower() in ("true", "1", "yes")

    # Filtro de semanas para trabajos finales y evidencias (ej: "S3,S8")
    TRABAJO_WEEKS_FILTER = os.getenv("TRABAJO_WEEKS_FILTER", "")

    # Rellena la rúbrica para Trabajos Finales (S3, S6, S8)
    ENABLE_TRABAJO_RUBRICA_EXPORT = os.getenv("ENABLE_TRABAJO_RUBRICA_EXPORT", "False").lower() in ("true", "1", "yes")

    # Exporta y sube evidencias de aprendizaje (S8) a Moodle
    # Fuente: workspace/COURSEID/actividades-trabajo-final/SX_Evidencia.html
    # Destino: actividad Moodle "SX | Evidencia"
    ENABLE_EVIDENCIA_EXPORT = os.getenv("ENABLE_EVIDENCIA_EXPORT", "False").lower() in ("true", "1", "yes")

    # Rellena la rúbrica para Evidencias de Aprendizaje (S8)
    ENABLE_EVIDENCIA_RUBRICA_EXPORT = os.getenv("ENABLE_EVIDENCIA_RUBRICA_EXPORT", "False").lower() in ("true", "1", "yes")

    # Filtro de semanas para rúbricas (ej: "S1,S2,S3,S4,S5,S6,S7,S8" o "S3,S8")
    # Si está vacío, se procesan todas las semanas configuradas por defecto para cada tipo.
    RUBRICA_WEEKS_FILTER = os.getenv("RUBRICA_WEEKS_FILTER", "")

    # -------------------------------------------- FASE 04 PODCAST PREGUNTAS -------------------------------------------------------------------------------------------------------------------------
    # Genera y sube el archivo HTML de SX | Recursos usando la plantilla,
    # Sacar de Propuesta metodologica, subir a Drive, limpiar, descargar como csv. pasar a carpeta recursos guardar como recursos.csv
    ENABLE_RECURSOS_HTML_EXPORT = os.getenv("ENABLE_RECURSOS_HTML_EXPORT", "False").lower() in ("true", "1", "yes")

    # ------------------------------------------------------------------------------------------------ FASE 05 BANCO DE PREGUNTAS ------------------------------------------------------------------------------------------------
    # Borra preguntas existentes antes de importar
    ENABLE_CLEAR_PUNTOS_EXTRAS = os.getenv("ENABLE_CLEAR_PUNTOS_EXTRAS", "False").lower() in ("true", "1", "yes")

    # Convierte archivos DOCX a GIFT y los sube a los Puntos Extras en Moodle.
    # info se encuentra en items de evalacion/examenes
    # Dejar archivos en workspace/ID_CURSO/evaluacion/Puntos extra_S*.docx
    ENABLE_PUNTOS_EXTRAS_EXPORT = os.getenv("ENABLE_PUNTOS_EXTRAS_EXPORT", "False").lower() in ("true", "1", "yes")

    # Convierte archivos DOCX a GIFT y los sube al Examen de recuperación en Moodle.
    # Dejar archivos en workspace/ID_CURSO/evaluacion/recuperacion/ExamenRecuperación_S*.docx
    ENABLE_RECUPERACION_EXPORT = os.getenv("ENABLE_RECUPERACION_EXPORT", "False").lower() in ("true", "1", "yes")

    # ------------------------------------------------------------------------------------------------ FASE 06 BANCO DE CONFIG FINAL ----------------------------------------------------------------------------
    # Elimina todos los items del curso que contengan la palabra "VIR" ALERTA!!!!!!!!!!!!!!!!!!
    ENABLE_CONFIGURACION_FINAL = os.getenv("ENABLE_CONFIGURACION_FINAL", "False").lower() in ("true", "1", "yes")

    # Configura competencias del curso y de actividades específicas
    ENABLE_AJUSTE_COMPETENCIAS = os.getenv("ENABLE_AJUSTE_COMPETENCIAS", "False").lower() in ("true", "1", "yes")

    # Depositphotos Credentials

    # Global explicit wait timeout in seconds

    # List of Moodle course IDs to iterate over
