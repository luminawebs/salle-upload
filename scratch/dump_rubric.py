import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from config.settings import Config
from config.driver_setup import get_driver
from actions.moodle_actions import MoodleAutomation, login_to_moodle, navigate_to_course
from actions.actividad_rubrica_actions import _find_assign_url, _navigate_to_rubric_editor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def dump_rubric():
    driver = get_driver()
    try:
        login_to_moodle(driver, Config.MOODLE_URL, Config.MOODLE_USER, Config.MOODLE_PASSWORD, 10)
        course_id = 4737
        url = _find_assign_url(driver, course_id, "S2", 2, 10)
        if url:
            if _navigate_to_rubric_editor(driver, url, 10):
                time.sleep(2)
                html = driver.find_element(By.CSS_SELECTOR, "table.criteria").get_attribute("outerHTML")
                with open("scratch/rubric_dump.html", "w", encoding="utf-8") as f:
                    f.write(html)
                logger.info("Dumped to scratch/rubric_dump.html")
            else:
                logger.error("Could not navigate to rubric editor")
        else:
            logger.error("Could not find S2 activity")
    finally:
        driver.quit()

if __name__ == "__main__":
    os.makedirs("scratch", exist_ok=True)
    dump_rubric()
