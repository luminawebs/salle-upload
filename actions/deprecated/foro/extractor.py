import time
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

from config.settings import Config

logger = logging.getLogger(__name__)

def extract_foro_content(driver, week_name, wait_time=10):
    """
    Navigates to the `VIR - FORO GRUPAL` resource for a given week and extracts its raw HTML content.
    """
    wait = WebDriverWait(driver, wait_time)
    logger.info(f"Searching for 'VIR - FORO GRUPAL' in '{week_name}'")
    
    try:
        # 1. Locate the section wrapper for the week
        try:
            quick_wait = WebDriverWait(driver, 3)
            quick_xpath = f"//li[contains(@class, 'section')]//*[contains(., '{week_name}')]"
            quick_wait.until(EC.presence_of_element_located((By.XPATH, quick_xpath)))
        except TimeoutException:
            logger.warning(f"Section '{week_name}' not found on the page.")
            return None

        title_xpath = f"//li[contains(@class, 'section')]//*[contains(@class, 'sectionname') or self::h3 or self::h4][contains(., '{week_name}')]"
        title_element = wait.until(EC.presence_of_element_located((By.XPATH, title_xpath)))
        section_li = title_element.find_element(By.XPATH, "./ancestor::li[contains(@class, 'section')]")
        
        # 2. Locate only the VIR - FORO GRUPAL activity for extraction
        activity_xpath = (
            ".//li[contains(@class, 'activity')]//*[contains(@class, 'instancename') "
            "and contains(text(), 'VIR - FORO GRUPAL')]"
        )
        try:
            activity_title = section_li.find_element(By.XPATH, activity_xpath)
            logger.info("Found forum resource for extraction: 'VIR - FORO GRUPAL'")
        except Exception:
            logger.warning(f"'VIR - FORO GRUPAL' not found in '{week_name}'.")
            return None
            
        activity_li = activity_title.find_element(By.XPATH, "./ancestor::li[contains(@class, 'activity')]")
        
        dropdown_toggle = activity_li.find_element(By.CSS_SELECTOR, "a.dropdown-toggle[title='Editar'], a[aria-label='Editar']")
        try:
            wait.until(EC.element_to_be_clickable(dropdown_toggle)).click()
        except WebDriverException:
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
            except WebDriverException:
                driver.execute_script("arguments[0].click();", edit_option)
            
        logger.info("Waiting for resource settings page to load...")
        time.sleep(3)  # Give JS editor time to sync
        
        # Try page[text] first (Moodle Page activity), then introeditor (Moodle Forum activity)
        raw_html = None
        for textarea_css in [
            "textarea[name='page[text]']",          # Moodle mod_page (most likely)
            "textarea[name='introeditor[text]']",   # Moodle mod_forum description
        ]:
            try:
                textarea = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, textarea_css))
                )
                raw_html = driver.execute_script("return arguments[0].value;", textarea)
                if raw_html and raw_html.strip():
                    logger.info(f"Extracted from '{textarea_css}' — {len(raw_html)} chars.")
                    break
                else:
                    logger.info(f"Textarea '{textarea_css}' was empty, trying next...")
                    raw_html = None
            except TimeoutException:
                logger.info(f"Textarea '{textarea_css}' not found, trying next...")
                
        if not raw_html or not raw_html.strip():
            logger.info("All textareas empty or not found, checking Atto/TinyMCE editor...")
            try:
                atto_editor = driver.find_element(By.CSS_SELECTOR, ".editor_atto_content, .tox-edit-area__iframe")
                if atto_editor.tag_name.lower() == "iframe":
                    driver.switch_to.frame(atto_editor)
                    raw_html = driver.find_element(By.TAG_NAME, "body").get_attribute("innerHTML")
                    driver.switch_to.default_content()
                else:
                    raw_html = driver.execute_script("return arguments[0].innerHTML;", atto_editor)
                logger.info(f"Extracted from Atto editor — {len(raw_html) if raw_html else 0} chars.")
            except Exception as e:
                logger.error(f"Could not extract content from any editor for '{week_name}': {e}")
                if use_new_tab:
                    driver.close()
                    driver.switch_to.window(original_window)
                else:
                    driver.back()
                return None
                
        if not raw_html or not raw_html.strip():
            logger.error(f"No content found in any editor field for '{week_name}'.")
            if use_new_tab:
                driver.close()
                driver.switch_to.window(original_window)
            else:
                driver.back()
            return None
            
        if use_new_tab:
            driver.close()
            driver.switch_to.window(original_window)
        else:
            driver.back()
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "body.path-course-view")))
        
        return raw_html
        
    except Exception as e:
        logger.error(f"Failed to extract foro from '{week_name}': {e}")
        try:
            if "original_window" in locals() and "use_new_tab" in locals() and use_new_tab:
                if driver.current_window_handle != original_window:
                    driver.close()
                    driver.switch_to.window(original_window)
            elif "modedit.php" in driver.current_url:
                driver.back()
        except Exception:
            pass
        return None
