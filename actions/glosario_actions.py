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
        time.sleep(2)
        
        # Search for Glosario
        search_box = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input.search-input, input[placeholder*='Buscar']")))
        search_box.clear()
        search_box.send_keys("Glosario")
        time.sleep(1)
        
        # Click the Glosario option
        glosario_option = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".option[data-name='glossary'], .option[title='Glosario'], .modicon_glossary, .modtype_glossary a")))
        driver.execute_script("arguments[0].click();", glosario_option)
        
        # Wait for the settings page to load
        name_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input#id_name")))
        name_input.clear()
        name_input.send_keys("GLOSARIO")
        
        # Click "Guardar cambios y mostrar"
        submit_btn = driver.find_element(By.CSS_SELECTOR, "#id_submitbutton, input[name='submitbutton']")
        driver.execute_script("arguments[0].scrollIntoView();", submit_btn)
        time.sleep(1)
        submit_btn.click()
        
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
        # The user provided: <button type="submit" class="btn btn-secondary">Importar entradas</button>
        # in a form to mod/glossary/import.php
        import_btn = wait.until(EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Importar entradas')] | //a[contains(@href, 'import.php')]")))
        driver.execute_script("arguments[0].click();", import_btn)
        
        # Wait for the file picker
        file_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file'][name*='file']")))
        
        # Unhide the file input if Moodle hides it
        driver.execute_script("arguments[0].style.display = 'block';", file_input)
        driver.execute_script("arguments[0].style.visibility = 'visible';", file_input)
        driver.execute_script("arguments[0].style.opacity = '1';", file_input)
        
        # Send keys to the input
        file_input.send_keys(os.path.abspath(xml_path))
        time.sleep(1)
        
        # Submit the import
        submit_import_btn = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#id_submitbutton, input[type='submit']")))
        submit_import_btn.click()
        time.sleep(3)
        
        # Optionally click 'Continuar'
        try:
            continue_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Continuar')]")
            continue_btn.click()
            time.sleep(2)
        except NoSuchElementException:
            pass
            
        logger.info(f"Successfully imported Glosario entries from {xml_path}")
        return True
    except Exception as e:
        logger.error(f"Error importing Glosario entries: {e}")
        return False
