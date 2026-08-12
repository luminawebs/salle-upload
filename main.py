import logging
import json
import os
from core.driver_setup import get_driver
from core.data_parser import run_docx_parsing_workflow, run_docx_splitting_workflow
from core.unidades_intro_parser import run_unidades_intro_splitting_workflow
from actions.moodle_actions import MoodleAutomation, dismiss_moodle_error_overlays
from actions.format_actions import set_buttons_format
from actions.course_format_initial_actions import set_custom_sections_format
from actions.course_format_final_actions import set_final_buttons_format
from actions.section_actions import enable_edit_mode
from actions.docx_upload_actions import run_docx_upload_workflow
from actions.cuestionario_export_actions import run_cuestionario_export_workflow
from actions.unidades_intro_actions import upload_unidades_intro_for_course
from actions.docx_rubrica_actions import run_docx_rubrica_upload_workflow
from actions.structure_actions import run_course_structure_creation_workflow
from actions.materiales_estudio_actions import run_materiales_estudio_workflow
from actions.glosario_actions import create_glosario_activity
from config.settings import Config
from core.debug_utils import capture_debug_state

# Setup base logging for the application
logging.basicConfig(
    level=logging.INFO, format="%(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("main")



def run_workflow_safely(driver, course_id, moodle, workflow_name, workflow_func, *args, **kwargs):
    try:
        workflow_func(*args, **kwargs)
    except Exception as e:
        import traceback
        logger.error(f"Error executing {workflow_name} for course {course_id}: {e}")
        logger.error(traceback.format_exc())
        try:
            from actions.moodle_actions import dismiss_moodle_error_overlays
            dismiss_moodle_error_overlays(driver)
            logger.info(f"Navigating back to course {course_id} home after {workflow_name} error...")
            moodle.navigate_to_course(course_id)
        except Exception as inner_e:
            logger.warning(f"Failed to recover after {workflow_name} error: {inner_e}")
def main():
    logger.info("Starting Moodle Automation Script...")

    # Pre-flight check for necessary credentials
    if not Config.MOODLE_USERNAME or not Config.MOODLE_PASSWORD:
        logger.error("Credentials are not set. Check your .env setup.")
        return

    courses_to_process = Config.COURSES_TO_PROCESS

    infografia_base_url = None
    actividad_source = "local"
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

        for course_id in courses_to_process:
            course_log_dir = os.path.join(Config.WORKSPACE_DIR, str(course_id), "logs")
            os.makedirs(course_log_dir, exist_ok=True)
            log_file_path = os.path.join(course_log_dir, "execution.log")
            
            file_handler = logging.FileHandler(log_file_path, mode='a', encoding='utf-8')
            file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
            logging.getLogger().addHandler(file_handler)

            try:
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
                    or getattr(Config, "ENABLE_DOCX_RUBRICA_UPLOAD", False)
                    or getattr(Config, "ENABLE_ACTIVITY_COMPLETION_UPDATE", False)
                ):
                    edit_enabled = enable_edit_mode(
                        driver, wait_time=Config.EXPLICIT_WAIT_TIME
                    )
                    if not edit_enabled:
                        logger.warning("Could not enable edit mode. Skipping interactions for this course.")
                        continue
                if getattr(Config, "ENABLE_COURSE_FORMAT_CHANGE", False):
                    logger.info("Switching course format to 'Secciones personalizadas'...")
                    try:
                        set_custom_sections_format(driver, course_id, wait_time=Config.EXPLICIT_WAIT_TIME)
                        capture_debug_state(driver, course_id, 'set_custom_sections_format', is_error=False)
                    except Exception as e:
                        import traceback
                        capture_debug_state(driver, course_id, 'set_custom_sections_format_error', is_error=True)
                        logger.error(f"Error executing set_custom_sections_format for course {course_id}: {e}")
                        logger.error(traceback.format_exc())
                        try:
                            dismiss_moodle_error_overlays(driver)
                            logger.info(f"Navigating back to course {course_id} home after error...")
                            moodle.navigate_to_course(course_id)
                        except Exception:
                            pass
                else:
                    logger.info("Course format change workflow is disabled via config.")

                if getattr(Config, "ENABLE_COURSE_STRUCTURE_CREATION", False) and edit_enabled:
                    logger.info("Executing course structure creation workflow...")
                    try:
                        run_course_structure_creation_workflow(driver, course_id, wait_time=Config.EXPLICIT_WAIT_TIME)
                        capture_debug_state(driver, course_id, 'course_structure_creation', is_error=False)
                    except Exception as e:
                        import traceback
                        capture_debug_state(driver, course_id, 'course_structure_creation_error', is_error=True)
                        logger.error(f"Error executing run_course_structure_creation_workflow for course {course_id}: {e}")
                        logger.error(traceback.format_exc())
                        try:
                            dismiss_moodle_error_overlays(driver)
                            logger.info(f"Navigating back to course {course_id} home after error...")
                            moodle.navigate_to_course(course_id)
                        except Exception:
                            pass
                elif not getattr(Config, "ENABLE_COURSE_STRUCTURE_CREATION", False):
                    logger.info("Course structure creation workflow is disabled via config.")

                if getattr(Config, "ENABLE_DOCX_UPLOAD_HTML", False):
                    logger.info("Executing DOCX HTML upload workflow...")
                    try:
                        run_docx_upload_workflow(driver, course_id, wait_time=getattr(Config, "EXPLICIT_WAIT_TIME", 10))
                        capture_debug_state(driver, course_id, 'docx_upload', is_error=False)
                    except Exception as e:
                        import traceback
                        capture_debug_state(driver, course_id, 'docx_upload_error', is_error=True)
                        logger.error(f"Error executing run_docx_upload_workflow for course {course_id}: {e}")
                        logger.error(traceback.format_exc())
                        try:
                            dismiss_moodle_error_overlays(driver)
                            logger.info(f"Navigating back to course {course_id} home after error...")
                            moodle.navigate_to_course(course_id)
                        except Exception:
                            pass
                else:
                    logger.info("DOCX HTML upload workflow is disabled via config.")

                if getattr(Config, "ENABLE_GLOSARIO_UPLOAD", False) and edit_enabled:
                    logger.info("Executing Glosario creation workflow...")
                    try:
                        glosario_xml_path = os.path.join(Config.WORKSPACE_DIR, str(course_id), "glosario", "glosario_import.xml")
                        create_glosario_activity(driver, course_id, glosario_xml_path, wait_time=getattr(Config, "EXPLICIT_WAIT_TIME", 10))
                        capture_debug_state(driver, course_id, 'glosario_upload', is_error=False)
                    except Exception as e:
                        import traceback
                        capture_debug_state(driver, course_id, 'glosario_upload_error', is_error=True)
                        logger.error(f"Error executing create_glosario_activity for course {course_id}: {e}")
                        logger.error(traceback.format_exc())
                        try:
                            dismiss_moodle_error_overlays(driver)
                            logger.info(f"Navigating back to course {course_id} home after error...")
                            moodle.navigate_to_course(course_id)
                        except Exception:
                            pass
                elif not getattr(Config, "ENABLE_GLOSARIO_UPLOAD", False):
                    logger.info("Glosario creation workflow is disabled via config.")

                if getattr(Config, "ENABLE_MATERIALES_ESTUDIO_EXPORT", False) and edit_enabled:
                    logger.info("Executing Materiales de Estudio workflow...")
                    try:
                        run_materiales_estudio_workflow(driver, course_id, wait_time=getattr(Config, "EXPLICIT_WAIT_TIME", 10))
                        capture_debug_state(driver, course_id, 'materiales_estudio', is_error=False)
                    except Exception as e:
                        import traceback
                        capture_debug_state(driver, course_id, 'materiales_estudio_error', is_error=True)
                        logger.error(f"Error executing run_materiales_estudio_workflow for course {course_id}: {e}")
                        logger.error(traceback.format_exc())
                        try:
                            dismiss_moodle_error_overlays(driver)
                            logger.info(f"Navigating back to course {course_id} home after error...")
                            moodle.navigate_to_course(course_id)
                        except Exception:
                            pass
                elif not getattr(Config, "ENABLE_MATERIALES_ESTUDIO_EXPORT", False):
                    logger.info("Materiales de Estudio workflow is disabled via config.")


                if (getattr(Config, "ENABLE_CUESTIONARIO_EXPORT", False) or getattr(Config, "ENABLE_CUESTIONARIO_GRADE_UPDATE", False)) and edit_enabled:
                    logger.info("Executing Cuestionario export/grade workflow...")
                    try:
                        run_cuestionario_export_workflow(driver, course_id, wait_time=getattr(Config, "EXPLICIT_WAIT_TIME", 10))
                        capture_debug_state(driver, course_id, 'cuestionario_export', is_error=False)
                    except Exception as e:
                        import traceback
                        capture_debug_state(driver, course_id, 'cuestionario_export_error', is_error=True)
                        logger.error(f"Error executing run_cuestionario_export_workflow for course {course_id}: {e}")
                        logger.error(traceback.format_exc())
                        try:
                            dismiss_moodle_error_overlays(driver)
                            logger.info(f"Navigating back to course {course_id} home after error...")
                            moodle.navigate_to_course(course_id)
                        except Exception:
                            pass
                elif not (getattr(Config, "ENABLE_CUESTIONARIO_EXPORT", False) or getattr(Config, "ENABLE_CUESTIONARIO_GRADE_UPDATE", False)):
                    logger.info("Cuestionario export/grade workflow is disabled via config.")

                if getattr(Config, "ENABLE_UNIDADES_INTRO_UPLOAD", False):
                    logger.info("Executing Unidades Intro upload workflow...")
                    try:
                        upload_unidades_intro_for_course(driver, course_id, wait_time=Config.EXPLICIT_WAIT_TIME)
                        capture_debug_state(driver, course_id, 'unidades_intro_upload', is_error=False)
                    except Exception as e:
                        import traceback
                        capture_debug_state(driver, course_id, 'unidades_intro_upload_error', is_error=True)
                        logger.error(f"Error executing upload_unidades_intro_for_course for course {course_id}: {e}")
                        logger.error(traceback.format_exc())
                        try:
                            dismiss_moodle_error_overlays(driver)
                            logger.info(f"Navigating back to course {course_id} home after error...")
                            moodle.navigate_to_course(course_id)
                        except Exception:
                            pass
                else:
                    logger.info("Unidades Intro upload workflow is disabled via config.")

                if getattr(Config, "ENABLE_DOCX_RUBRICA_UPLOAD", False):
                    logger.info("Executing DOCX Rubrica upload workflow...")
                    try:
                        run_docx_rubrica_upload_workflow(driver, course_id, wait_time=Config.EXPLICIT_WAIT_TIME)
                        capture_debug_state(driver, course_id, 'docx_rubrica_upload', is_error=False)
                    except Exception as e:
                        import traceback
                        capture_debug_state(driver, course_id, 'docx_rubrica_upload_error', is_error=True)
                        logger.error(f"Error executing run_docx_rubrica_upload_workflow for course {course_id}: {e}")
                        logger.error(traceback.format_exc())
                        try:
                            dismiss_moodle_error_overlays(driver)
                            logger.info(f"Navigating back to course {course_id} home after error...")
                            moodle.navigate_to_course(course_id)
                        except Exception:
                            pass
                else:
                    logger.info("DOCX Rubrica upload workflow is disabled via config.")

                if getattr(Config, "ENABLE_ACTIVITY_COMPLETION_UPDATE", False) and edit_enabled:
                    logger.info("Executing activity completion update workflow...")
                    from actions.activity_completion_actions import run_activity_completion_workflow
                    run_activity_completion_workflow(
                        driver, course_id, wait_time=Config.EXPLICIT_WAIT_TIME
                    )
                    capture_debug_state(driver, course_id, 'activity_completion', is_error=False)
                elif not getattr(Config, "ENABLE_ACTIVITY_COMPLETION_UPDATE", False):
                    logger.info("Activity completion update workflow is disabled via config.")

                if getattr(Config, "ENABLE_COURSE_FORMAT_CHANGE", False):
                    logger.info("Reverting course format back to 'Formato de botones'...")
                    try:
                        set_buttons_format(driver, course_id, wait_time=Config.EXPLICIT_WAIT_TIME)
                        capture_debug_state(driver, course_id, 'set_buttons_format', is_error=False)
                    except Exception as e:
                        import traceback
                        capture_debug_state(driver, course_id, 'set_buttons_format_error', is_error=True)
                        logger.error(f"Error executing set_buttons_format for course {course_id}: {e}")
                        logger.error(traceback.format_exc())
                        try:
                            dismiss_moodle_error_overlays(driver)
                            logger.info(f"Navigating back to course {course_id} home after error...")
                            moodle.navigate_to_course(course_id)
                        except Exception:
                            pass
                else:
                    logger.info("Course format revert workflow is disabled via config.")
                    
                if getattr(Config, "ENABLE_FINAL_COURSE_FORMAT_BUTTONS", False):
                    logger.info("Setting final course format to 'Formato de botones'...")
                    try:
                        set_final_buttons_format(driver, course_id, wait_time=Config.EXPLICIT_WAIT_TIME)
                        capture_debug_state(driver, course_id, 'set_final_buttons_format', is_error=False)
                    except Exception as e:
                        import traceback
                        capture_debug_state(driver, course_id, 'set_final_buttons_format_error', is_error=True)
                        logger.error(f"Error executing set_final_buttons_format for course {course_id}: {e}")
                        logger.error(traceback.format_exc())
                elif not getattr(Config, "ENABLE_FINAL_COURSE_FORMAT_BUTTONS", False):
                    logger.info("Final course format workflow is disabled via config.")
                dismiss_moodle_error_overlays(driver)
            except Exception as e:
                import traceback
                capture_debug_state(driver, course_id, 'general_course_error', is_error=True)
                logger.error(f"Error processing course {course_id}: {e}")
                logger.error(traceback.format_exc())
                try:
                    dismiss_moodle_error_overlays(driver)
                    logger.info(f"Navigating back to course {course_id} home after error...")
                    moodle.navigate_to_course(course_id)
                except Exception:
                    pass
                finally:
                    logging.getLogger().removeHandler(file_handler)
                    file_handler.close()
                    continue

            # Ensure the handler is removed if the try block completes successfully
            logging.getLogger().removeHandler(file_handler)
            file_handler.close()

    except Exception as e:
        import traceback
        logger.error(f"An unexpected error occurred during automation: {e}\n{traceback.format_exc()}")
    finally:
        logger.info("Shutting down WebDriver...")
        driver.quit()


if __name__ == "__main__":
    main()
