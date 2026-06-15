import logging
import json
import os
from core.driver_setup import get_driver
from core.data_parser import run_docx_parsing_workflow, run_docx_splitting_workflow
from core.unidades_intro_parser import run_unidades_intro_splitting_workflow
from actions.moodle_actions import MoodleAutomation
from actions.section_actions import (
    enable_edit_mode,
    rename_all_sections,
    update_all_section_descriptions,
)
from actions.infografia.infografia_actions import run_infografia_export_workflow
from actions.depositphotos_actions import run_depositphotos_workflow
from actions.foro import run_foro_export_workflow
from actions.actualidad_actions import run_actualidad_export_workflow
from actions.preguntas_actions import run_preguntas_workflow
from actions.recursos_apoyo_actions import run_recursos_apoyo_workflow
from actions.recursos_apoyo_edit_actions import run_recursos_apoyo_edit_classes_workflow
from actions.actividad_actions import run_actividad_export_workflow
from actions.trabajo_actions import run_trabajo_export_workflow
from actions.evidencia_actions import run_evidencia_export_workflow
from actions.actividad_recursos_actions import run_actividad_recursos_workflow
from actions.actividad_rubrica_actions import run_actividad_rubrica_workflow
from actions.puntos_extras_actions import run_puntos_extras_workflow
from actions.recuperacion_actions import run_recuperacion_export_workflow
from actions.docx_upload_actions import run_docx_upload_workflow
from actions.cuestionario_export_actions import run_cuestionario_export_workflow
from actions.unidades_intro_actions import upload_unidades_intro_for_course
from actions.docx_rubrica_actions import run_docx_rubrica_upload_workflow
from actions.recursos_semana_actions import run_recursos_html_export_workflow
from actions.configuracion_final_actions import run_configuracion_final_workflow
from actions.competencias_actions import run_ajuste_competencias_workflow
from actions.structure_actions import run_course_structure_creation_workflow
from config.settingsSALLE import ConfigSALLE as Config

# Setup base logging for the application
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("main")


def main():
    logger.info("Starting Moodle Automation Script...")

    # Pre-flight check for necessary credentials
    if not Config.MOODLE_USERNAME or not Config.MOODLE_PASSWORD:
        logger.error("Credentials are not set. Check your .env setup.")
        return

    courses_to_process = Config.COURSES_TO_PROCESS

    infografia_base_url = None
    if getattr(Config, "ENABLE_INFOGRAFIA_EXPORT", False):
        infografia_base_url = input("Please provide the base URL for infografia images (e.g., https://contenidomoodle.s3.amazonaws.com/UNIMINUTO_VIRTUAL/pregrado/COMMARINT/): ")
        if not infografia_base_url.endswith('/'):
            infografia_base_url += '/'

    actividad_source = "local"
    if getattr(Config, "ENABLE_ACTIVIDAD_EXPORT", False):
        while True:
            ans = input("Are the activities 'local' or 'remote' on VIR - ACTIVIDAD (From each week 2,4,6,8)? (local/remote): ").strip().lower()
            if ans in ["local", "remote"]:
                actividad_source = ans
                break
            print("Please enter 'local' or 'remote'.")

    logger.info("Initializing WebDriver...")
    driver = get_driver()

    try:
        # Pass the initialized driver into our action class
        moodle = MoodleAutomation(driver)

        # Step 1: Perform login once
        success = moodle.login(Config.MOODLE_USERNAME, Config.MOODLE_PASSWORD)
        if not success:
            logger.error("Aborting process since login failed.")
            return

        # Step 2: Iterate through all target courses
        for course_id in courses_to_process:
            logger.info(f"--- Processing Course ID: {course_id} ---")
            logger.info(f"Nombre del curso: Curso {course_id}")
            course_loaded = moodle.navigate_to_course(course_id)

            if not course_loaded:
                logger.error(
                    f"Could not load course {course_id}. Skipping all workflows for this course."
                )
                continue

            if getattr(Config, "ENABLE_DOCX_PARSING", False):
                logger.info("Executing DOCX extraction workflow...")
                run_docx_parsing_workflow(course_id)
            else:
                logger.info("DOCX extraction workflow is disabled via config.")

            if getattr(Config, "ENABLE_DOCX_SPLITTING_HTML", False):
                logger.info("Executing DOCX splitting workflow...")
                run_docx_splitting_workflow(course_id)
            else:
                logger.info("DOCX splitting workflow is disabled via config.")

            if getattr(Config, "ENABLE_UNIDADES_INTRO_SPLIT", False):
                logger.info("Executing Unidades Intro splitting workflow...")
                run_unidades_intro_splitting_workflow(course_id)
            else:
                logger.info("Unidades Intro splitting workflow is disabled via config.")

            # Upload workflow moved to after edit mode

            # --- Insert specific course interactions here ---
            # Ensure edit mode is enabled if we need to do either workflow
            edit_enabled = False
            if (
                getattr(Config, "ENABLE_COURSE_STRUCTURE_CREATION", False)
                or getattr(Config, "ENABLE_DOCX_UPLOAD_HTML", False)
                or getattr(Config, "ENABLE_CUESTIONARIO_EXPORT", False)
                or getattr(Config, "ENABLE_CUESTIONARIO_GRADE_UPDATE", False)
                or getattr(Config, "ENABLE_UNIDADES_INTRO_UPLOAD", False)
                or getattr(Config, "ENABLE_SECTION_RENAME", False)
                or getattr(Config, "ENABLE_GENERATE_HTML_INTRO", False)
                or getattr(Config, "ENABLE_GENERATE_HTML_INTRO_GENERAL", False)
                or getattr(Config, "ENABLE_INFOGRAFIA_EXPORT", False)
                or getattr(Config, "ENABLE_FORO_EXPORT", False)
                or getattr(Config, "ENABLE_ACTUALIDAD_EXPORT", False)
                or getattr(Config, "ENABLE_PREGUNTAS_EXPORT", False)
                or getattr(Config, "ENABLE_RECURSOS_APOYO_EXPORT", False)
                or getattr(Config, "ENABLE_RECURSOS_APOYO_EDIT_CLASSES", False)
                or getattr(Config, "ENABLE_ACTIVIDAD_EXPORT", False)
                or getattr(Config, "ENABLE_ACTIVIDAD_RECURSOS_EXPORT", False)
                or getattr(Config, "ENABLE_ACTIVIDAD_RUBRICA_EXPORT", False)
                or getattr(Config, "ENABLE_TRABAJO_EXPORT", False)
                or getattr(Config, "ENABLE_TRABAJO_RUBRICA_EXPORT", False)
                or getattr(Config, "ENABLE_EVIDENCIA_RUBRICA_EXPORT", False)
                or getattr(Config, "ENABLE_EVIDENCIA_EXPORT", False)
                or getattr(Config, "ENABLE_RECURSOS_HTML_EXPORT", False)
                or getattr(Config, "ENABLE_DOCX_RUBRICA_UPLOAD", False)
                or getattr(Config, "ENABLE_CLEAR_PUNTOS_EXTRAS", False)
                or getattr(Config, "ENABLE_PUNTOS_EXTRAS_EXPORT", False)
                or getattr(Config, "ENABLE_RECUPERACION_EXPORT", False)
                or getattr(Config, "ENABLE_AJUSTE_COMPETENCIAS", False)
                or getattr(Config, "ENABLE_CONFIGURACION_FINAL", False)
                or getattr(Config, "ENABLE_ACTIVITY_COMPLETION_UPDATE", False)
            ):
                edit_enabled = enable_edit_mode(
                    driver, wait_time=Config.EXPLICIT_WAIT_TIME
                )
                if not edit_enabled:
                    logger.warning("Could not enable edit mode. Skipping interactions for this course.")
                    continue

            if getattr(Config, "ENABLE_COURSE_STRUCTURE_CREATION", False) and edit_enabled:
                logger.info("Executing course structure creation workflow...")
                run_course_structure_creation_workflow(driver, course_id, wait_time=Config.EXPLICIT_WAIT_TIME)
            elif not getattr(Config, "ENABLE_COURSE_STRUCTURE_CREATION", False):
                logger.info("Course structure creation workflow is disabled via config.")

            if getattr(Config, "ENABLE_DOCX_UPLOAD_HTML", False):
                logger.info("Executing DOCX HTML upload workflow...")
                run_docx_upload_workflow(driver, course_id, wait_time=getattr(Config, "EXPLICIT_WAIT_TIME", 10))
            else:
                logger.info("DOCX HTML upload workflow is disabled via config.")

            if (getattr(Config, "ENABLE_CUESTIONARIO_EXPORT", False) or getattr(Config, "ENABLE_CUESTIONARIO_GRADE_UPDATE", False)) and edit_enabled:
                logger.info("Executing Cuestionario export/grade workflow...")
                run_cuestionario_export_workflow(driver, course_id, wait_time=getattr(Config, "EXPLICIT_WAIT_TIME", 10))
            elif not (getattr(Config, "ENABLE_CUESTIONARIO_EXPORT", False) or getattr(Config, "ENABLE_CUESTIONARIO_GRADE_UPDATE", False)):
                logger.info("Cuestionario export/grade workflow is disabled via config.")

            if getattr(Config, "ENABLE_UNIDADES_INTRO_UPLOAD", False):
                logger.info("Executing Unidades Intro upload workflow...")
                upload_unidades_intro_for_course(driver, course_id, wait_time=Config.EXPLICIT_WAIT_TIME)
            else:
                logger.info("Unidades Intro upload workflow is disabled via config.")

            if getattr(Config, "ENABLE_DOCX_RUBRICA_UPLOAD", False):
                logger.info("Executing DOCX Rubrica upload workflow...")
                run_docx_rubrica_upload_workflow(driver, course_id, wait_time=Config.EXPLICIT_WAIT_TIME)
            else:
                logger.info("DOCX Rubrica upload workflow is disabled via config.")

            if getattr(Config, "ENABLE_SECTION_RENAME", False) and edit_enabled:
                logger.info("Executing section rename workflow...")
                rename_all_sections(driver, wait_time=Config.EXPLICIT_WAIT_TIME)
            elif not getattr(Config, "ENABLE_SECTION_RENAME", False):
                logger.info("Section rename workflow is disabled via config.")

            if getattr(Config, "ENABLE_SECTION_DESCRIPTION_UPDATE", False) and edit_enabled:
                logger.info("Executing section description update workflow...")
                
                descriptions_mapping = {}
                csv_path = os.path.join("assets", str(course_id), "Propuesta_Metodológica.csv")
                json_path = os.path.join("assets", str(course_id), "contenidos.json")
                
                if os.path.exists(csv_path):
                    import csv
                    try:
                        try:
                            f = open(csv_path, 'r', encoding='utf-8-sig')
                            headers = next(csv.reader(f))
                        except UnicodeDecodeError:
                            f = open(csv_path, 'r', encoding='cp1252')
                            headers = next(csv.reader(f))
                            
                        f.seek(0)
                        reader = csv.reader(f)
                        headers = next(reader)
                        
                        nombre_idx = next((i for i, h in enumerate(headers) if 'NOMBRE DE LA SEMANA' in h), None)
                        semana_idx = next((i for i, h in enumerate(headers) if '# SEMANA DE ESTUDIO' in h), None)
                        
                        if nombre_idx is not None and semana_idx is not None:
                            for row in reader:
                                if len(row) > max(semana_idx, nombre_idx):
                                    semana = row[semana_idx].strip()
                                    nombre = row[nombre_idx].strip()
                                    if semana.isdigit():
                                        descriptions_mapping[f"Semana {semana}"] = nombre
                        f.close()
                    except Exception as e:
                        logger.error(f"Failed to read CSV {csv_path}: {e}")

                # Fallback to json if mapping couldn't be loaded
                if not descriptions_mapping and os.path.exists(json_path):
                    with open(json_path, "r", encoding="utf-8") as f:
                        contenidos_data = json.load(f)
                        if "nombre" in contenidos_data:
                            logger.info(f"Nombre del curso: {contenidos_data['nombre']}")
                            
                        descriptions_mapping = {
                            week: data["nombre"]
                            for week, data in contenidos_data.items()
                            if "nombre" in data and isinstance(data, dict)
                        }

                if descriptions_mapping:
                    update_all_section_descriptions(
                        driver,
                        course_id,
                        descriptions_mapping,
                        wait_time=Config.EXPLICIT_WAIT_TIME,
                    )
                else:
                    logger.warning(
                        f"No valid mapping found for course {course_id} (checked CSV and JSON). Skipping description update."
                    )
            elif not getattr(Config, "ENABLE_SECTION_DESCRIPTION_UPDATE", False):
                logger.info(
                    "Section description update workflow is disabled via config."
                )

            if getattr(Config, "ENABLE_GENERATE_HTML_INTRO", False) and edit_enabled:
                logger.info("Executing local HTML intro generation workflow...")
                from actions.introduccion_actions import run_generar_introduccion_workflow
                run_generar_introduccion_workflow(driver, course_id, wait_time=Config.EXPLICIT_WAIT_TIME)
            elif not getattr(Config, "ENABLE_GENERATE_HTML_INTRO", False):
                logger.info("Local HTML intro generation workflow is disabled via config.")

            if getattr(Config, "ENABLE_GENERATE_HTML_INTRO_GENERAL", False) and edit_enabled:
                logger.info("Executing general HTML intro generation workflow...")
                from actions.introduccion_general_actions import run_generar_introduccion_general_workflow
                run_generar_introduccion_general_workflow(driver, course_id, wait_time=Config.EXPLICIT_WAIT_TIME)
            elif not getattr(Config, "ENABLE_GENERATE_HTML_INTRO_GENERAL", False):
                logger.info("General HTML intro generation workflow is disabled via config.")

            if getattr(Config, "ENABLE_INFOGRAFIA_EXPORT", False) and edit_enabled:
                logger.info("Executing infografia export workflow...")
                run_infografia_export_workflow(
                    driver, course_id, infografia_base_url, wait_time=Config.EXPLICIT_WAIT_TIME
                )
            elif not getattr(Config, "ENABLE_INFOGRAFIA_EXPORT", False):
                logger.info("Infografia export workflow is disabled via config.")

            if getattr(Config, "ENABLE_FORO_EXPORT", False) and edit_enabled:
                logger.info("Executing foro export workflow...")
                run_foro_export_workflow(driver, course_id)
            elif not getattr(Config, "ENABLE_FORO_EXPORT", False):
                logger.info("Foro export workflow is disabled via config.")

            if getattr(Config, "ENABLE_ACTUALIDAD_EXPORT", False) and edit_enabled:
                logger.info("Executing actualidad export workflow...")
                run_actualidad_export_workflow(
                    driver, course_id, wait_time=Config.EXPLICIT_WAIT_TIME
                )
            elif not getattr(Config, "ENABLE_ACTUALIDAD_EXPORT", False):
                logger.info("Actualidad export workflow is disabled via config.")

            if getattr(Config, "ENABLE_PREGUNTAS_EXPORT", False) and edit_enabled:
                logger.info("Executing preguntas export workflow...")
                run_preguntas_workflow(
                    driver, course_id, wait_time=Config.EXPLICIT_WAIT_TIME
                )
            elif not getattr(Config, "ENABLE_PREGUNTAS_EXPORT", False):
                logger.info("Preguntas export workflow is disabled via config.")

            if getattr(Config, "ENABLE_RECURSOS_APOYO_EXPORT", False) and edit_enabled:
                logger.info("Executing recursos apoyo export workflow...")
                run_recursos_apoyo_workflow(
                    driver, course_id, wait_time=Config.EXPLICIT_WAIT_TIME
                )
            elif not getattr(Config, "ENABLE_RECURSOS_APOYO_EXPORT", False):
                logger.info("Recursos apoyo export workflow is disabled via config.")

            if getattr(Config, "ENABLE_RECURSOS_APOYO_EDIT_CLASSES", False) and edit_enabled:
                logger.info("Executing recursos apoyo edit classes workflow...")
                run_recursos_apoyo_edit_classes_workflow(
                    driver, course_id, wait_time=Config.EXPLICIT_WAIT_TIME
                )
            elif not getattr(Config, "ENABLE_RECURSOS_APOYO_EDIT_CLASSES", False):
                logger.info("Recursos apoyo edit classes workflow is disabled via config.")

            if getattr(Config, "ENABLE_ACTIVIDAD_EXPORT", False) and edit_enabled:
                logger.info("Executing actividad export workflow...")
                run_actividad_export_workflow(
                    driver, course_id, actividad_source, wait_time=Config.EXPLICIT_WAIT_TIME
                )
            elif not getattr(Config, "ENABLE_ACTIVIDAD_EXPORT", False):
                logger.info("Actividad export workflow is disabled via config.")

            if getattr(Config, "ENABLE_ACTIVIDAD_RECURSOS_EXPORT", False) and edit_enabled:
                logger.info("Executing actividad recursos export workflow...")
                run_actividad_recursos_workflow(
                    driver, course_id, wait_time=Config.EXPLICIT_WAIT_TIME
                )
            elif not getattr(Config, "ENABLE_ACTIVIDAD_RECURSOS_EXPORT", False):
                logger.info("Actividad recursos export workflow is disabled via config.")

            if getattr(Config, "ENABLE_ACTIVIDAD_RUBRICA_EXPORT", False) and edit_enabled:
                logger.info("Executing actividad rúbrica export workflow...")
                run_actividad_rubrica_workflow(
                    driver, course_id, workflow_type="actividad", wait_time=Config.EXPLICIT_WAIT_TIME
                )
            elif not getattr(Config, "ENABLE_ACTIVIDAD_RUBRICA_EXPORT", False):
                logger.info("Actividad rúbrica export workflow is disabled via config.")

            if getattr(Config, "ENABLE_TRABAJO_RUBRICA_EXPORT", False) and edit_enabled:
                logger.info("Executing trabajo rúbrica export workflow...")
                run_actividad_rubrica_workflow(
                    driver, course_id, workflow_type="trabajo", wait_time=Config.EXPLICIT_WAIT_TIME
                )
            elif not getattr(Config, "ENABLE_TRABAJO_RUBRICA_EXPORT", False):
                logger.info("Trabajo rúbrica export workflow is disabled via config.")

            if getattr(Config, "ENABLE_EVIDENCIA_RUBRICA_EXPORT", False) and edit_enabled:
                logger.info("Executing evidencia rúbrica export workflow...")
                run_actividad_rubrica_workflow(
                    driver, course_id, workflow_type="evidencia", wait_time=Config.EXPLICIT_WAIT_TIME
                )
            elif not getattr(Config, "ENABLE_EVIDENCIA_RUBRICA_EXPORT", False):
                logger.info("Evidencia rúbrica export workflow is disabled via config.")


            if getattr(Config, "ENABLE_TRABAJO_EXPORT", False) and edit_enabled:
                logger.info("Executing trabajo final export workflow...")
                run_trabajo_export_workflow(
                    driver, course_id, workflow_type="trabajo", wait_time=Config.EXPLICIT_WAIT_TIME
                )
            elif not getattr(Config, "ENABLE_TRABAJO_EXPORT", False):
                logger.info("Trabajo final export workflow is disabled via config.")

            if getattr(Config, "ENABLE_EVIDENCIA_EXPORT", False) and edit_enabled:
                logger.info("Executing evidencia export workflow...")
                run_evidencia_export_workflow(
                    driver, course_id, wait_time=Config.EXPLICIT_WAIT_TIME
                )
            elif not getattr(Config, "ENABLE_EVIDENCIA_EXPORT", False):
                logger.info("Evidencia export workflow is disabled via config.")



            if getattr(Config, "ENABLE_RECURSOS_HTML_EXPORT", False) and edit_enabled:
                logger.info("Executing recursos HTML export workflow...")
                run_recursos_html_export_workflow(
                    driver, course_id, wait_time=Config.EXPLICIT_WAIT_TIME
                )
            elif not getattr(Config, "ENABLE_RECURSOS_HTML_EXPORT", False):
                logger.info("Recursos HTML export workflow is disabled via config.")

            if getattr(Config, "ENABLE_CLEAR_PUNTOS_EXTRAS", False) and edit_enabled:
                logger.info("Executing clear puntos extras questions workflow...")
                from actions.puntos_extras_actions import clear_puntos_extras_questions
                clear_puntos_extras_questions(
                    driver, course_id, wait_time=Config.EXPLICIT_WAIT_TIME
                )
            elif not getattr(Config, "ENABLE_CLEAR_PUNTOS_EXTRAS", False):
                logger.info("Clear puntos extras questions workflow is disabled via config.")

            if getattr(Config, "ENABLE_PUNTOS_EXTRAS_EXPORT", False) and edit_enabled:
                logger.info("Executing puntos extras export workflow...")
                run_puntos_extras_workflow(
                    driver, course_id, wait_time=Config.EXPLICIT_WAIT_TIME
                )
            elif not getattr(Config, "ENABLE_PUNTOS_EXTRAS_EXPORT", False):
                logger.info("Puntos extras export workflow is disabled via config.")

            if getattr(Config, "ENABLE_RECUPERACION_EXPORT", False) and edit_enabled:
                logger.info("Executing recuperacion export workflow...")
                run_recuperacion_export_workflow(
                    driver, course_id, wait_time=Config.EXPLICIT_WAIT_TIME
                )
            elif not getattr(Config, "ENABLE_RECUPERACION_EXPORT", False):
                logger.info("Recuperacion export workflow is disabled via config.")

            if getattr(Config, "ENABLE_AJUSTE_COMPETENCIAS", False) and edit_enabled:
                logger.info("Executing ajuste competencias workflow...")
                run_ajuste_competencias_workflow(
                    driver, course_id, wait_time=Config.EXPLICIT_WAIT_TIME
                )
            elif not getattr(Config, "ENABLE_AJUSTE_COMPETENCIAS", False):
                logger.info("Ajuste competencias workflow is disabled via config.")

            if getattr(Config, "ENABLE_CONFIGURACION_FINAL", False) and edit_enabled:
                logger.info("Executing configuracion final workflow...")
                run_configuracion_final_workflow(
                    driver, course_id, wait_time=Config.EXPLICIT_WAIT_TIME
                )
            elif not getattr(Config, "ENABLE_CONFIGURACION_FINAL", False):
                logger.info("Configuracion final workflow is disabled via config.")

            if getattr(Config, "ENABLE_ACTIVITY_COMPLETION_UPDATE", False) and edit_enabled:
                logger.info("Executing activity completion update workflow...")
                from actions.activity_completion_actions import run_activity_completion_workflow
                run_activity_completion_workflow(
                    driver, course_id, wait_time=Config.EXPLICIT_WAIT_TIME
                )
            elif not getattr(Config, "ENABLE_ACTIVITY_COMPLETION_UPDATE", False):
                logger.info("Activity completion update workflow is disabled via config.")

            if getattr(Config, "ENABLE_DEPOSITPHOTOS_DOWNLOAD", False):
                logger.info("Executing Depositphotos download workflow...")
                run_depositphotos_workflow(driver, course_id)
            else:
                logger.info("Depositphotos download workflow is disabled via config.")

    except Exception as e:
        import traceback
        logger.error(f"An unexpected error occurred during automation: {e}\n{traceback.format_exc()}")
    finally:
        logger.info("Shutting down WebDriver...")
        driver.quit()


if __name__ == "__main__":
    main()
