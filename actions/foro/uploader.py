import time
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

from actions.moodle_actions import navigate_to_course
from config.settings import Config

logger = logging.getLogger(__name__)

def upload_foro_content(driver, course_id, week_name, resource_name, html_content, wait_time=10):
    """
    Uploads the provided HTML content to the specified forum resource's 
    'Descripción' (introeditor) WYSIWYG editor for the specified week.
    """
    wait = WebDriverWait(driver, wait_time)
    logger.info(f"Uploading content to '{resource_name}' in '{week_name}'")
    
    try:
        # 0. Ensure we are at the course view to start fresh
        if "course/view.php" not in driver.current_url:
            navigate_to_course(driver, Config.MOODLE_URL, course_id, wait_time)

        # 1. Locate the section wrapper for the week
        try:
            # First handle any accidental alerts
            try:
                alert = driver.switch_to.alert
                logger.warning(f"Unexpected alert found: {alert.text}. Dismissing.")
                alert.dismiss()
            except:
                pass

            quick_wait = WebDriverWait(driver, 5)
            # Find the section by its name (Semana X)
            section_xpath = f"//li[contains(@class, 'section')][descendant::*[contains(@class, 'sectionname') or self::h3 or self::h4][contains(., '{week_name}')]]"
            section_li = quick_wait.until(EC.presence_of_element_located((By.XPATH, section_xpath)))
        except TimeoutException:
            logger.warning(f"Section '{week_name}' not found. Verify if sections were renamed correctly.")
            return False

        # 2. Locate the Forum resource (e.g., "S3 | Foro")
        activity_xpath = f".//li[contains(@class, 'activity')]//*[contains(@class, 'instancename') and contains(text(), '{resource_name}')]"
        try:
            activity_title = section_li.find_element(By.XPATH, activity_xpath)
        except Exception:
            logger.warning(f"Resource '{resource_name}' not found in '{week_name}'.")
            return False
            
        activity_li = activity_title.find_element(By.XPATH, "./ancestor::li[contains(@class, 'activity')]")
        
        # 3. Open "Editar" -> "Editar ajustes"
        dropdown_toggle = activity_li.find_element(By.CSS_SELECTOR, "a.dropdown-toggle[title='Editar'], a[aria-label='Editar']")
        try:
            wait.until(EC.element_to_be_clickable(dropdown_toggle)).click()
        except:
            driver.execute_script("arguments[0].click();", dropdown_toggle)
            
        edit_option_xpath = ".//a[contains(@class, 'dropdown-item') and (contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'editar ajustes') or contains(@href, 'modedit.php'))]"
        edit_option = wait.until(lambda d: activity_li.find_element(By.XPATH, edit_option_xpath))
        edit_href = edit_option.get_attribute("href")
        
        original_window = driver.current_window_handle
        use_new_tab = Config.ENABLE_FORO_EXPORT and edit_href
        
        if use_new_tab:
            driver.execute_script("window.open(arguments[0], '_blank');", edit_href)
            for window_handle in driver.window_handles:
                if window_handle != original_window:
                    driver.switch_to.window(window_handle)
                    break
        else:
            try:
                wait.until(EC.element_to_be_clickable(edit_option)).click()
            except:
                driver.execute_script("arguments[0].click();", edit_option)
            
        # 4. Wait for the settings page to load
        logger.info("Waiting for resource settings page to load...")
        submit_btn_css = "#id_submitbutton, input[name='submitbutton'], button[name='submitbutton']"
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, submit_btn_css)))
        
        # 5. Handle the WYSIWYG editor (Descripción field / introeditor)
        # For Foros, the field name is 'introeditor[text]'
        textarea_css = "textarea[name='introeditor[text]']"
        try:
            # 5a. Update hidden textarea first
            textarea = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, textarea_css)))
            driver.execute_script("arguments[0].value = arguments[1];", textarea, html_content)
            
            # 5b. Update Atto visual editor if present
            try:
                atto_editor = driver.find_element(By.CSS_SELECTOR, ".editor_atto_content")
                driver.execute_script("arguments[0].innerHTML = arguments[1];", atto_editor, html_content)
                logger.info("Content set in Atto editor and textarea (introeditor).")
            except:
                logger.info("Atto editor not found, updated textarea directly.")
                
            # Trigger change events to notify Moodle's JS
            driver.execute_script(
                "var event = new Event('change', { bubbles: true });"
                "document.querySelector(arguments[0]).dispatchEvent(event);"
                "var inputEvent = new Event('input', { bubbles: true });"
                "document.querySelector(arguments[0]).dispatchEvent(inputEvent);"
                "if (typeof M !== 'undefined' && M.editor_atto) { "
                "  var id = document.querySelector('.editor_atto_content').id; "
                "  var editor = M.editor_atto.getEditor(id); "
                "  if (editor) { editor.updateFromTextArea(); } "
                "} ",
                textarea_css
            )
            time.sleep(2) # Wait for JS to process the content
        except Exception as e:
            logger.error(f"Failed to set editor content: {e}")
            if use_new_tab:
                driver.close()
                driver.switch_to.window(original_window)
            return False
            
        # 6. Save and return to course
        logger.info("Saving changes...")
        try:
            submit_btn = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, submit_btn_css)))
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", submit_btn)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", submit_btn)
        except Exception as e:
            logger.error(f"Could not find or click save button: {e}")
            if use_new_tab:
                driver.close()
                driver.switch_to.window(original_window)
            return False
            
        # Wait for redirection back to course view
        try:
            save_wait = WebDriverWait(driver, 40)
            save_wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "body.path-course-view, #region-main")))
            logger.info(f"Successfully uploaded content to '{week_name}'.")
            if use_new_tab:
                driver.close()
                driver.switch_to.window(original_window)
            return True
        except TimeoutException:
            if "course/view.php" in driver.current_url:
                logger.info(f"Redirection detected via URL for '{week_name}'.")
                if use_new_tab:
                    driver.close()
                    driver.switch_to.window(original_window)
                return True
            logger.error(f"Timeout waiting for redirection after saving '{week_name}'.")
            if use_new_tab:
                driver.close()
                driver.switch_to.window(original_window)
            return False

    except Exception as e:
        logger.error(f"Error during upload to '{week_name}': {e}")
        return False
