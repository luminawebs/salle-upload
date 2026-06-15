import os
import time
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from core.wysiwyg_handler import extract_html_from_wysiwyg, inject_html_into_wysiwyg

logger = logging.getLogger(__name__)

def click_edit_for_section(driver, section_prefix: str, wait_time: int = 10) -> bool:
    """
    Finds the Moodle section matching section_prefix (e.g. 'UNIDAD 1') and clicks 'Editar tema'.
    Case-insensitive search.
    """
    wait = WebDriverWait(driver, wait_time)
    try:
        lower_prefix = section_prefix.lower()
        # Find the li.section that contains the text
        xpath = f"//li[contains(@class, 'section') and .//h3[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{lower_prefix}')]]"
        
        try:
            section_element = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
        except TimeoutException:
            logger.error(f"Section matching '{section_prefix}' not found.")
            return False

        # Scroll into view
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", section_element)
        time.sleep(1)

        # Find the dropdown toggle for the section
        dropdown_xpath = ".//a[contains(@class, 'dropdown-toggle') and @role='button']"
        try:
            dropdown_toggle = section_element.find_element(By.XPATH, dropdown_xpath)
            driver.execute_script("arguments[0].click();", dropdown_toggle)
            time.sleep(1)
        except Exception as e:
            logger.warning(f"Dropdown toggle not found or unclickable: {e}")

        # Find 'Editar tema'
        edit_xpath = ".//a[contains(@href, 'editsection.php')]"
        try:
            edit_link = wait.until(EC.element_to_be_clickable(section_element.find_element(By.XPATH, edit_xpath)))
            driver.execute_script("arguments[0].click();", edit_link)
            return True
        except Exception as e:
            logger.error(f"Could not click 'Editar tema' for '{section_prefix}': {e}")
            return False

    except Exception as e:
        logger.error(f"Error finding/clicking edit for section '{section_prefix}': {e}")
        return False

def upload_unidades_intro_for_course(driver, course_id: int, wait_time: int = 15) -> bool:
    """
    Uploads the generated introduccion_unidad_N.html fragments to the Moodle section summaries.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    intro_dir = os.path.join(base_dir, "assets", str(course_id), "introduccion")

    if not os.path.exists(intro_dir):
        logger.warning(f"No introduccion directory found for course {course_id}. Skipping Unidades Intro upload.")
        return True

    files = [f for f in os.listdir(intro_dir) if f.startswith("introduccion_unidad_") and f.endswith(".html")]
    if not files:
        logger.info(f"No Unidad Introduccion HTML files found for course {course_id}.")
        return True

    wait = WebDriverWait(driver, wait_time)
    all_success = True

    for filename in sorted(files):
        # Extract the unit number from the filename
        # e.g. introduccion_unidad_1.html -> 1
        unit_num = filename.split("introduccion_unidad_")[1].split(".html")[0]
        section_prefix = f"UNIDAD {unit_num}"
        
        logger.info(f"Uploading {filename} to {section_prefix}...")

        # Failsafe: Ensure we are on the course page before finding the section
        if "course/view.php" not in driver.current_url:
            from config.settingsSALLE import ConfigSALLE
            logger.info("  Not on course view page, navigating back...")
            course_url = f"{ConfigSALLE.MOODLE_URL}/course/view.php?id={course_id}"
            driver.get(course_url)
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "body.path-course-view, #region-main")))
                time.sleep(2)
            except TimeoutException:
                logger.error(f"Failed to load course view page for {course_id}.")
                all_success = False
                continue

        if click_edit_for_section(driver, section_prefix, wait_time):
            # Wait for editor to load
            submit_btn_css = "#id_submitbutton, #id_submitbutton2, input[name='submitbutton'], input[name='submitbutton2'], button[name='submitbutton']"
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, submit_btn_css)))
            except TimeoutException:
                logger.error(f"Timeout waiting for editor page to load for {section_prefix}")
                all_success = False
                continue
            
            # Wait for TinyMCE/Atto
            try:
                editor_ready_css = ".tox-edit-area__iframe, .editor_atto_content, textarea[name='summary_editor[text]']"
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, editor_ready_css)))
                time.sleep(1)
            except Exception:
                pass

            file_path = os.path.join(intro_dir, filename)
            with open(file_path, "r", encoding="utf-8") as f:
                new_html = f.read()

            # Target section summary
            success = inject_html_into_wysiwyg(driver, new_html, wait_time, target_section="resumen")
            if success:
                logger.info(f"Success: {filename}")
            else:
                logger.error(f"Failed to inject HTML for {filename}")
                all_success = False
        else:
            logger.error(f"Could not open editor for {section_prefix}")
            all_success = False

    return all_success
