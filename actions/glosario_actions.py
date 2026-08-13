import os
import time
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

logger = logging.getLogger(__name__)

def create_glosario_activity(driver, course_id, xml_path, wait_time=10):
    """
    Creates a 'Glosario' activity in 'BIENVENIDOS AL CURSO' (section 0)
    and imports the entries from the given xml_path.
    """
    if not os.path.exists(xml_path):
        logger.warning(f"Glosario XML not found at {xml_path}. Skipping Glosario creation.")
        return False
        
    wait = WebDriverWait(driver, wait_time)
    
    # Navigate to course
    # Assuming we are in the course, but just to be sure we'll go to the section page or main course page
    # The caller must ensure we are logged in and on the course page.
    
    try:
        # Find section 0 add activity button
        section_0 = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "li#section-0, li[data-sectionnum='0'], div#section-0")))
        
        # Click the add activity button inside section 0
        try:
            add_btn = section_0.find_element(By.CSS_SELECTOR, ".section-modchooser-link, [data-action='open-chooser']")
            driver.execute_script("arguments[0].click();", add_btn)
        except NoSuchElementException:
            # Maybe editing is not turned on? Try turning it on if possible, but assume it's on for now
            logger.error("Could not find Add Activity button. Is editing turned on?")
            return False
            
        # Wait for the modchooser dialog
        logger.info("Waiting for modchooser dialog...")
        time.sleep(2)
        
        # Search for Glosario (Optional, Moodle 4.x feature)
        logger.info("Searching for Glosario in modchooser (if search box exists)...")
        try:
            search_box = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input.search-input, input[placeholder*='Buscar']")))
            search_box.clear()
            search_box.send_keys("Glosario")
            time.sleep(1)
        except TimeoutException:
            logger.info("Search box not found. Proceeding to find Glosario directly...")
        
        # Click the Glosario option
        logger.info("Clicking Glosario option...")
        try:
            # We target the anchor tag inside the option div that has data-internal="glossary"
            # Or the anchor tag that has href containing 'add=glossary'
            css = ".option[data-internal='glossary'] a, a[href*='add=glossary'], .option[data-name='glossary'], .modtype_glossary a"
            glosario_option = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, css)))
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", glosario_option)
            time.sleep(0.5)
            driver.execute_script("arguments[0].click();", glosario_option)
        except TimeoutException:
            # Fallback for Moodle 3.x / 4.x text search
            logger.info("CSS selectors failed, trying XPath fallback...")
            xpath = ".//div[contains(@class, 'optionname') and contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'glosario')]/ancestor::a"
            glosario_option = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", glosario_option)
            time.sleep(0.5)
            driver.execute_script("arguments[0].click();", glosario_option)
        
        # Wait for the settings page to load
        logger.info("Waiting for Glosario settings page...")
        name_input = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input#id_name")))
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", name_input)
        time.sleep(0.5)
        name_input.clear()
        name_input.send_keys("GLOSARIO")
        
        # Click "Guardar cambios y mostrar"
        logger.info("Saving Glosario activity...")
        submit_btn = driver.find_element(By.CSS_SELECTOR, "#id_submitbutton, input[name='submitbutton']")
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", submit_btn)
        time.sleep(1)
        driver.execute_script("arguments[0].click();", submit_btn)
        
        # Wait for the glosario page to load by waiting for the import entries button or admin menu
        time.sleep(3)
        
        # Now import entries
        return import_glosario_entries(driver, xml_path, wait_time)
        
    except Exception as e:
        logger.error(f"Error creating Glosario activity: {e}")
        return False

def import_glosario_entries(driver, xml_path, wait_time=10):
    wait = WebDriverWait(driver, wait_time)
    try:
        # Find the "Importar entradas" form/button
        logger.info("Looking for 'Importar entradas' button...")
        import_btn = wait.until(EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Importar entradas')] | //a[contains(@href, 'import.php')]")))
        driver.execute_script("arguments[0].click();", import_btn)
        
        # Wait for the file picker
        file_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file'][name*='file']")))
        
        # Unhide the file input if Moodle hides it
        driver.execute_script("arguments[0].style.display = 'block';", file_input)
        driver.execute_script("arguments[0].style.visibility = 'visible';", file_input)
        driver.execute_script("arguments[0].style.opacity = '1';", file_input)
        
        # Send keys to the input
        logger.info("Uploading XML file...")
        file_input.send_keys(os.path.abspath(xml_path))
        time.sleep(1)
        
        # Submit the import
        logger.info("Submitting glosario import form...")
        submit_import_btn = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#id_submitbutton, input[type='submit']")))
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", submit_import_btn)
        time.sleep(1)
        driver.execute_script("arguments[0].click();", submit_import_btn)
        time.sleep(3)
        
        # Optionally click 'Continuar'
        try:
            logger.info("Looking for 'Continuar' button...")
            continue_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Continuar')]")
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", continue_btn)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", continue_btn)
            time.sleep(2)
        except NoSuchElementException:
            logger.info("'Continuar' button not found, assuming success.")
            pass
            
        logger.info(f"Successfully imported Glosario entries from {xml_path}")
        return True
    except Exception as e:
        logger.error(f"Error importing Glosario entries: {e}")
        return False
