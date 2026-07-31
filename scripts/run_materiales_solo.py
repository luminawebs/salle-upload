import logging
import asyncio
import os
from dotenv import load_dotenv

from core.moodle_handler import MoodleHandler
from config.settings import Config
from actions.materiales_estudio_actions import run_materiales_estudio_workflow
from actions.section_actions import enable_edit_mode

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("run_materiales_solo")

def main():
    load_dotenv()
    
    logger.info("Initializing standalone Materiales de Estudio execution...")
    moodle = MoodleHandler()
    driver = None
    
    try:
        driver = moodle.setup_driver()
        moodle.login(driver)
        
        # Pull course IDs from config just like main.py
        courses = Config.COURSES_TO_PROCESS
        if not courses:
            logger.error("No courses configured in COURSES_TO_PROCESS")
            return
            
        for course_id in courses:
            logger.info(f"Navigating to course {course_id}...")
            moodle.navigate_to_course(course_id)
            
            logger.info("Enabling edit mode...")
            enable_edit_mode(driver, course_id, wait_time=10)
            
            logger.info(f"Running workflow for course {course_id}...")
            run_materiales_estudio_workflow(driver, course_id, wait_time=10)
            
    except Exception as e:
        logger.error(f"Error during execution: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        if driver:
            logger.info("Closing browser...")
            driver.quit()
        logger.info("Standalone execution finished.")

if __name__ == "__main__":
    main()
