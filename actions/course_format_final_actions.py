import logging
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from config.settings import Config

logger = logging.getLogger(__name__)

def set_final_buttons_format(driver, course_id, wait_time=10):
    """
    Enter 'Configuración' from the general course.
    Expand 'Formato de curso' (if not expanded).
    On Formato selector choose 'Formato de botones'.
    Wait for page to load again.
    Finally click on 'Guardar cambios y mostrar'.
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
            
        # Select 'Formato de botones' option by data-value
        logger.info("Selecting 'Formato de botones'...")
        buttons_option = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a[data-value='buttons']")))
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", buttons_option)
        time.sleep(0.5)
        
        # Click the option
        driver.execute_script("arguments[0].click();", buttons_option)
        
        # Wait for reload or UI update
        time.sleep(3)
        
        # Wait for page to load again (check for the save button)
        logger.info("Finding 'Guardar cambios y mostrar' button...")
        save_btn = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='saveanddisplay'], input#id_saveanddisplay")))
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", save_btn)
        time.sleep(0.5)
        
        logger.info("Clicking 'Guardar cambios y mostrar'...")
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
            
        logger.info("Successfully set course format to 'Formato de botones' and saved.")
        return True
        
    except Exception as e:
        logger.error(f"Error setting final buttons format for course {course_id}: {e}")
        return False
