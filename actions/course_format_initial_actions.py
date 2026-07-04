import logging
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from config.settingsSALLE import ConfigSALLE as Config

logger = logging.getLogger(__name__)

def set_custom_sections_format(driver, course_id, wait_time=10):
    """
    Enter 'Configuración' from the general course.
    Expand 'Formato de curso' (if not expanded).
    On Formato selector choose 'Secciones personalizadas'.
    Wait for page to load again.
    Finally click on 'Guardar cambios y mostrar' or 'Guardar y volver'.
    """
    wait = WebDriverWait(driver, wait_time)
    
    # Navigates to course edit (Configuración)
    edit_url = f"{Config.MOODLE_URL}/course/edit.php?id={course_id}"
    logger.info(f"Navigating to course settings for course {course_id}...")
    driver.get(edit_url)
    
    try:
        # Wait for the format section header
        wait.until(EC.presence_of_element_located((By.ID, "id_courseformathdrcontainer")))
        
        # Check if 'Formato de curso' is expanded
        toggle_link = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a[aria-controls='id_courseformathdrcontainer']")))
        if str(toggle_link.get_attribute("aria-expanded")).lower() == "false":
            logger.info("Expanding 'Formato de curso' section...")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", toggle_link)
            time.sleep(0.5)
            driver.execute_script("arguments[0].click();", toggle_link)
            time.sleep(1)
            
        # Select 'Secciones personalizadas' option by data-value or text
        logger.info("Selecting 'Secciones personalizadas'...")
        try:
            # Try to find the custom dropdown option by typical values
            customsections_option = wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, "a[data-value='customsections'], a[data-value='topics']")
            ))
        except:
            # Fallback to xpath by text or standard select option
            customsections_option = wait.until(EC.presence_of_element_located(
                (By.XPATH, "//a[contains(normalize-space(.), 'Secciones personalizadas')] | //option[contains(normalize-space(.), 'Secciones personalizadas')]")
            ))
            
        # Ensure it's selected properly (using JS click to handle both hidden standard options and custom dropdowns)
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", customsections_option)
        time.sleep(0.5)
        
        # Click the option
        if customsections_option.tag_name.lower() == 'option':
            logger.info("Selected a standard <option>. Setting 'selected' and triggering change event on parent <select>.")
            driver.execute_script("""
                arguments[0].selected = true;
                arguments[0].closest('select').dispatchEvent(new Event('change'));
            """, customsections_option)
        else:
            driver.execute_script("arguments[0].click();", customsections_option)
        
        # Wait for reload or UI update
        time.sleep(3)
        
        # Wait for page to load again (check for the save button)
        logger.info("Finding save button...")
        try:
            save_btn = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='saveanddisplay'], input#id_saveanddisplay")))
        except:
            save_btn = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='saveandreturn'], input#id_saveandreturn")))

        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", save_btn)
        time.sleep(0.5)
        
        logger.info("Clicking save button...")
        driver.execute_script("arguments[0].click();", save_btn)
        
        # Wait for the redirect/save to process
        try:
            wait.until(EC.staleness_of(save_btn))
        except:
            pass
        
        # Wait until we are redirected back to the course view
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "body.path-course-view")))
        except:
            pass
            
        logger.info("Successfully set course format to 'Secciones personalizadas' and saved.")
        return True
        
    except Exception as e:
        logger.error(f"Error setting custom sections format for course {course_id}: {e}")
        return False
