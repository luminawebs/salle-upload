import logging
import time
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

from actions.moodle_actions import MoodleAutomation, navigate_to_course
from actions.actividad_rubrica_actions import _navigate_to_rubric_editor, fill_rubric
from core.docx_rubrica_parser import parse_rubricas_from_docx
from config.settingsSALLE import ConfigSALLE

logger = logging.getLogger(__name__)

def _find_assign_url_by_name(driver, course_id: int, activity_name: str, wait_time: int) -> tuple[str | None, str | None]:
    """
    Navigate to the course and find the assign activity matching the given name (e.g., 'Actividad 1').
    Searches across all sections.
    """
    if "course/view.php" not in driver.current_url:
        navigate_to_course(driver, ConfigSALLE.MOODLE_URL, course_id, wait_time)

    # Wait for the course content to be fully loaded
    try:
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".course-content, #region-main"))
        )
    except TimeoutException:
        logger.warning("Course content timeout, continuing...")

    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            # Attempt to expand all sections if they are collapsed (Moodle 4.x)
            try:
                expand_all_btn = driver.find_elements(By.CSS_SELECTOR, "[data-action='toggleall'], .section-collapse-all, .toggle-all")
                for btn in expand_all_btn:
                    if btn.is_displayed() and "expand" in btn.get_attribute("aria-expanded") == "false" or "true" not in str(btn.get_attribute("aria-expanded")):
                        try:
                            driver.execute_script("arguments[0].click();", btn)
                            time.sleep(1)
                        except:
                            pass
            except:
                pass
                
            # Get ALL activities in the course
            activities = driver.find_elements(By.XPATH, "//li[contains(@class, 'activity')]")
            
            for activity in activities:
                try:
                    name_elem = activity.find_element(By.XPATH, ".//*[contains(@class, 'instancename')]")
                    name_text = name_elem.text.strip() if name_elem.text else name_elem.get_attribute("innerText")
                    
                    if name_text:
                        normalized_name = ' '.join(name_text.split()).lower()
                        normalized_search = ' '.join(activity_name.split()).lower()
                        
                        # We want to match the activity name flexibly, avoiding
                        # matching "Actividad 10" when searching for "Actividad 1".
                        words = normalized_search.split()
                        match = True
                        for w in words:
                            if w.isdigit():
                                if not re.search(rf'(^|\W){w}($|\W)', normalized_name):
                                    match = False
                                    break
                            else:
                                if w not in normalized_name:
                                    match = False
                                    break
                                    
                        if match:
                            # Find the primary link — must be mod/assign or mod/forum
                            for link in activity.find_elements(By.CSS_SELECTOR, "a.aalink, a.instancename"):
                                href = link.get_attribute("href") or ""
                                if "mod/assign" in href or "mod/forum" in href:
                                    if href.startswith("/"):
                                        base = re.match(r"(https?://[^/]+)", ConfigSALLE.MOODLE_URL).group(1)
                                        href = base + href
                                    logger.info(f"  ✓ Found URL for '{activity_name}' as '{name_text}': {href}")
                                    return href, name_text
                except Exception:
                    continue
                    
        except Exception as e:
            if attempt < max_attempts - 1:
                time.sleep(2)
            else:
                logger.warning(f"  Activity '{activity_name}' not found after {max_attempts} attempts.")
                return None, None

    return None, None

def run_docx_rubrica_upload_workflow(driver, course_id: int, wait_time: int = 15):
    """
    Workflow to parse rubrics from the DOCX and upload them to the corresponding Actividad assignments.
    """
    logger.info("Starting DOCX Rubrica upload workflow...")
    
    # 1. Parse the rubrics from the extracted DOCX
    rubricas_dict = parse_rubricas_from_docx(course_id)
    if not rubricas_dict:
        logger.warning("No rubrics found in the DOCX for this course. Skipping upload.")
        return

    # 2. Iterate and upload
    for act_num, criteria_list in rubricas_dict.items():
        activity_name = f"ACTIVIDAD {act_num}"
        logger.info(f"Processing Rubrica for {activity_name} ({len(criteria_list)} criteria)...")

        assign_url, full_activity_name = _find_assign_url_by_name(driver, course_id, activity_name, wait_time)
        if not assign_url:
            # Fallback check for mixed case
            assign_url, full_activity_name = _find_assign_url_by_name(driver, course_id, f"Actividad {act_num}", wait_time)

        if not assign_url:
            logger.error(f"Could not find Moodle assignment for {activity_name}. Skipping rubric.")
            continue

        # Navigate to the editor
        success_nav = _navigate_to_rubric_editor(driver, assign_url, wait_time)
        if not success_nav:
            logger.error(f"Failed to navigate to the rubric editor for {activity_name}.")
            continue

        # Fill and save the rubric
        try:
            rubric_title = full_activity_name if full_activity_name else activity_name
            success = fill_rubric(driver, criteria_list, wait_time, rubric_name=rubric_title)
            if success:
                logger.info(f"Successfully uploaded rubric for {rubric_title}.")
            else:
                logger.error(f"Failed to upload rubric for {rubric_title}.")
        except Exception as e:
            logger.error(f"Exception while filling rubric for {activity_name}: {e}")
