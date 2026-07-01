import logging
import time
from core.wysiwyg_handler import inject_html_into_wysiwyg
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, WebDriverException

logger = logging.getLogger(__name__)

def enable_edit_mode(driver, wait_time=10):
    """
    Enables Moodle editing mode if it's not already active.
    It targets the toggle input 'input[name="setmode"]' typically found in Moodle 4+.
    """
    wait = WebDriverWait(driver, wait_time)
    logger.info("Checking editing mode status...")
    
    try:
        # Check if already in editing mode via body class 'editing'
        body = driver.find_element(By.TAG_NAME, "body")
        if "editing" in body.get_attribute("class").split():
            logger.info("Editing mode is already active.")
            return True
            
        # Locate the switch toggle
        toggle = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='setmode']")))
        
        # Check if the input itself is checked
        if toggle.get_attribute("checked"):
            logger.info("Edit toggle is already checked.")
            return True

        # Try to click it. Sometimes it's hidden under a label wrapper
        try:
            wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[name='setmode']"))).click()
        except WebDriverException:
            # Fallback to JS click if element is obscured or not interactable
            driver.execute_script("arguments[0].click();", toggle)

        # Wait for UI to update (either body gets 'editing' class or page reloads)
        wait.until(lambda d: "editing" in d.find_element(By.TAG_NAME, "body").get_attribute("class").split())
        logger.info("Successfully enabled editing mode.")
        return True

    except TimeoutException:
        logger.warning("Timeout while trying to enable edit mode. Checking fallback states...")
        # Sometimes the page reloads unexpectedly, check again
        try:
            if "editing" in driver.find_element(By.TAG_NAME, "body").get_attribute("class").split():
                return True
        except:
            pass
        return False
    except Exception as e:
        if "Read timed out" in str(e) or "timeout" in str(e).lower():
            logger.error(f"Error enabling edit mode (Browser connection timed out or closed): {e}")
        else:
            logger.error(f"Error enabling edit mode: {e}")
        return False


def edit_section_name(driver, current_name, new_name, wait_time=10):
    """
    Renames a specific section inline using the quick edit (pen) icon.
    Robust handling of dynamic elements and AJAX updates.
    """
    wait = WebDriverWait(driver, wait_time)
    logger.info(f"Renaming section: '{current_name}' -> '{new_name}'")
    
    try:
        # 1. Locate the section wrapper containing the text
        # Using XPath for text matching, since CSS lacks text() selector. 
        # Focusing on headers or standard sectionname classes to avoid matching random content.
        title_xpath = (
            f"//li[contains(@class, 'section')]//*[contains(@class, 'sectionname') or self::h3 or self::h4]"
            f"[contains(., '{current_name}')]"
        )
        title_element = wait.until(EC.presence_of_element_located((By.XPATH, title_xpath)))
        
        # 2. Scope down to the specific section card/wrapper (li.section)
        section_li = title_element.find_element(By.XPATH, "./ancestor::li[contains(@class, 'section')]")
        
        # 3. Locate the in-line edit icon (pen icon) inside that section
        # Avoid generic "Edit" matches that catch the general section dropdown menu.
        # Targeted towards the specific quick-edit pencil structure: class="quickediticon"
        section_edit_icon = section_li.find_element(
            By.CSS_SELECTOR, ".quickediticon, [data-action='edittitle'], .edit-icon, i.fa-pen, i.fa-pencil"
        )
        
        # Click the edit icon securely
        try:
            wait.until(EC.element_to_be_clickable(section_edit_icon)).click()
        except WebDriverException:
            driver.execute_script("arguments[0].click();", section_edit_icon)

        # 4. Wait for the quick-edit text input to appear for this section
        input_css = "input[type='text']:not(.hidden), input.inplaceeditable"
        input_field = wait.until(lambda d: section_li.find_element(By.CSS_SELECTOR, input_css))
        wait.until(EC.visibility_of(input_field))

        # 5. Clear and enter new text
        # Using Keys.CONTROL + 'a' instead of .clear() as .clear() can be unreliable with JS listeners in Moodle
        input_field.send_keys(Keys.CONTROL + "a")
        input_field.send_keys(Keys.DELETE)
        input_field.send_keys(new_name)
        
        # 6. Confirm changes
        input_field.send_keys(Keys.RETURN)
        
        # 7. Wait for the new title to appear (confirming AJAX save success)
        new_title_xpath = f".//*[(contains(@class, 'sectionname') or self::h3 or self::h4) and contains(., '{new_name}')]"
        wait.until(lambda d: section_li.find_element(By.XPATH, new_title_xpath).is_displayed())
        
        logger.info(f"Successfully renamed to '{new_name}'")
        return True
        
    except TimeoutException:
        logger.error(f"Timeout occurred trying to locate or rename '{current_name}'.")
        return False
    except Exception as e:
        logger.error(f"Failed to rename '{current_name}': {e}")
        return False


def rename_all_sections(driver, wait_time=10):
    """
    Iterates over a mapping representing the old and new section names.
    Attempts to rename every section and logs success/failure without interrupting the process.
    """
    # Generating 0 to 20 just in case. The prompt said
    # Unidad 0 -> General
    # Unidad N -> Semana N
    mapping = {"Unidad 0": "General"}
    for i in range(1, 20):
        mapping[f"Unidad {i}"] = f"Semana {i}"
    
    results = {}
    
    from actions.moodle_actions import ensure_section_visible
    
    for old_name, new_name in mapping.items():
        ensure_section_visible(driver, old_name, wait_time=5)
        # First we can do a quick check if old_name exists before attempting to wait the full time
        try:
            # If not found immediately (within 2 seconds), continue to next
            quick_wait = WebDriverWait(driver, 2)
            quick_xpath = f"//li[contains(@class, 'section')]//*[contains(., '{old_name}')]"
            quick_wait.until(EC.presence_of_element_located((By.XPATH, quick_xpath)))
        except TimeoutException:
            # Section not found, skip it
            continue
            
        success = edit_section_name(driver, old_name, new_name, wait_time)
        results[f"{old_name} -> {new_name}"] = success
        
        if success:
            # Brief pause to let UI settle, avoiding AJAX collision or stale elements
            time.sleep(1)
            
    # Reporting
    logger.info("=== Renaming Operation Summary ===")
    for action, state in results.items():
        status = "OK" if state else "FAIL"
        logger.info(f"[{status}] {action}")
        
    return results


def edit_section_description(driver, section_name, new_description, wait_time=10):
    """
    Edits the description (wysiwyg) of a specific section.
    """
    wait = WebDriverWait(driver, wait_time)
    logger.info(f"Updating description for '{section_name}'")
    
    try:
        # Locate the section wrapper containing the text
        title_xpath = (
            f"//li[contains(@class, 'section')]//*[contains(@class, 'sectionname') or self::h3 or self::h4]"
            f"[contains(., '{section_name}')]"
        )
        title_element = wait.until(EC.presence_of_element_located((By.XPATH, title_xpath)))
        section_li = title_element.find_element(By.XPATH, "./ancestor::li[contains(@class, 'section')]")
        
        # Locate the 'Editar' dropdown menu toggle
        dropdown_toggle = section_li.find_element(By.CSS_SELECTOR, "a.dropdown-toggle[title='Editar'], a[aria-label='Editar']")
        
        # Click the dropdown toggle
        try:
            wait.until(EC.element_to_be_clickable(dropdown_toggle)).click()
        except WebDriverException:
            driver.execute_script("arguments[0].click();", dropdown_toggle)
            
        # Wait for the dropdown menu and click 'Editar tema' or 'Editar sección'
        edit_option_xpath = ".//a[contains(@class, 'dropdown-item') and (contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'editar tema') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'editar secci') or contains(@href, 'editsection.php'))]"
        edit_option = wait.until(lambda d: section_li.find_element(By.XPATH, edit_option_xpath))
        try:
            wait.until(EC.element_to_be_clickable(edit_option)).click()
        except WebDriverException:
            driver.execute_script("arguments[0].click();", edit_option)
            
        # Ensure submit button is present before injecting
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='submitbutton'], button[name='submitbutton'], #id_submitbutton")))
        
        # Use our centralized WYSIWYG handler
        success = inject_html_into_wysiwyg(driver, new_description, wait_time, target_section="descripcion")
        if not success:
            logger.error(f"WYSIWYG injection failed for '{section_name}'")
            return False
            
        # Wait to be back on the course page
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "body.path-course-view")))
        
        logger.info(f"Successfully updated description for '{section_name}'")
        return True
        
    except TimeoutException:
        logger.error(f"Timeout occurred trying to update description for '{section_name}'.")
        return False
    except Exception as e:
        logger.error(f"Failed to update description for '{section_name}': {e}")
        return False


def update_all_section_descriptions(driver, course_id, descriptions_mapping, wait_time=10):
    """
    Iterates over a mapping representing the section names and their new descriptions.
    """
    from actions.moodle_actions import navigate_to_course
    from config.settings import Config
    
    results = {}
    from actions.moodle_actions import ensure_section_visible
    
    for section_name, new_desc in descriptions_mapping.items():
        ensure_section_visible(driver, section_name, wait_time=5)
        try:
            quick_wait = WebDriverWait(driver, 2)
            quick_xpath = f"//li[contains(@class, 'section')]//*[contains(., '{section_name}')]"
            quick_wait.until(EC.presence_of_element_located((By.XPATH, quick_xpath)))
        except TimeoutException:
            continue
            
        success = edit_section_description(driver, section_name, new_desc, wait_time)
        results[f"{section_name} (desc)"] = success
        
        if success:
            time.sleep(1)
            # Ensure we navigate back to the main course page
            navigate_to_course(driver, Config.MOODLE_URL, course_id, wait_time)
            
    logger.info("=== Description Update Summary ===")
    for action, state in results.items():
        status = "OK" if state else "FAIL"
        logger.info(f"[{status}] {action}")
        
    return results
