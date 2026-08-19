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
        # Wait for section 0 to be present
        section_0_selector = "li#section-0, li[data-sectionnum='0'], div#section-0"
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, section_0_selector)))
        
        # Click the add activity button inside section 0
        try:
            add_btn_selector = "button.activity-add, a.section-modchooser-link:not([data-action='addSection']), button.section-modchooser-link, [data-action='open-chooser']"
            
            # Wait until at least one button is present within section 0 to avoid race conditions
            wait.until(lambda d: len(d.find_element(By.CSS_SELECTOR, section_0_selector).find_elements(By.CSS_SELECTOR, add_btn_selector)) > 0)
            
            # Re-fetch to avoid stale elements
            section_0 = driver.find_element(By.CSS_SELECTOR, section_0_selector)
            add_btns = section_0.find_elements(By.CSS_SELECTOR, add_btn_selector)
            
            if not add_btns:
                logger.error("Could not find Add Activity button. Is editing turned on?")
                return False
                
            add_btn = add_btns[-1] # ALWAYS click the LAST one to append to the bottom!
            
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", add_btn)
            time.sleep(1)
            
            # Log what button we are clicking
            logger.info(f"Found Add Activity button in Section 0: {add_btn.text.strip() or 'No Text'} (HTML: {add_btn.get_attribute('outerHTML')[:100]}...)")
            
            try:
                wait.until(EC.element_to_be_clickable(add_btn)).click()
            except Exception:
                driver.execute_script("arguments[0].click();", add_btn)
                
        except Exception as e:
            logger.error(f"Error finding/clicking Add Activity button: {e}")
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
        href = None
        original_window = driver.current_window_handle
        
        try:
            # Robust selection similar to structure_actions.py
            chooser = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".modchooser, .modal-dialog, .modal-content, [data-region='chooserdialogue']")))
            time.sleep(1) # Wait for AJAX/JS to populate the options
            
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".modchooser .option, .modchooser .modchooser-item, .modal-dialog .option, .modal-dialog .modchooser-item, [data-region='chooserdialogue'] .option")))
            except TimeoutException:
                pass
                
            options = chooser.find_elements(By.CSS_SELECTOR, ".option a, .option button, .option label, .modchooser-item, .option")
            
            keywords = ["glossary", "glosario"]
            found_glosario = False
            found_options_debug = []
            
            for option in options:
                text = option.text.lower()
                opt_href = option.get_attribute("href") or ""
                data_name = option.get_attribute("data-name") or ""
                
                found_options_debug.append(f"text='{text}', href='{opt_href}', data-name='{data_name}'")
                
                if any(k in text for k in keywords) or any(k in opt_href for k in keywords) or any(k in data_name.lower() for k in keywords):
                    href = opt_href
                    if href and "javascript" not in href.lower():
                        logger.info(f"[Tab Manager] Opening Glosario settings in a NEW TAB (href: {href})...")
                        driver.execute_script(f"window.open('{href}', '_blank');")
                        driver.switch_to.window(driver.window_handles[-1])
                        found_glosario = True
                        break
                    else:
                        logger.info("[Tab Manager] No href found. Clicking Glosario option in SAME tab...")
                        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", option)
                        time.sleep(0.5)
                        try:
                            option.click()
                        except Exception:
                            driver.execute_script("arguments[0].click();", option)
                        found_glosario = True
                        break
            
            if not found_glosario:
                logger.error("Could not find Glosario activity type in the chooser.")
                logger.debug(f"Available options in chooser: {found_options_debug[:10]}")
                try:
                    chooser.find_element(By.CSS_SELECTOR, ".close, button[data-action='hide']").click()
                except:
                    pass
                raise TimeoutException("Glosario option not found in modchooser.")
                
        except TimeoutException:
            logger.error("Timeout waiting for modchooser options or Glosario not found.")
            raise
        
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
        success = import_glosario_entries(driver, xml_path, wait_time)
        
        if href and len(driver.window_handles) > 1:
            logger.info("[Tab Manager] Closing new tab and switching back to original window...")
            driver.close()
            driver.switch_to.window(original_window)
            
        return success
        
    except Exception as e:
        logger.error(f"Error creating Glosario activity: {e}")
        # Make sure we don't strand the user in a broken tab
        if 'original_window' in locals() and len(driver.window_handles) > 1 and driver.current_window_handle != original_window:
            logger.warning("[Tab Manager] Error occurred. Closing current tab to recover state...")
            driver.close()
            driver.switch_to.window(original_window)
        return False

def import_glosario_entries(driver, xml_path, wait_time=10):
    wait = WebDriverWait(driver, wait_time)
    try:
        # Find the "Importar entradas" form/button
        logger.info("Looking for 'Importar entradas' button...")
        import_btn = wait.until(EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Importar entradas')] | //a[contains(@href, 'import.php')]")))
        driver.execute_script("arguments[0].click();", import_btn)
        
        # Wait for the Moodle file picker choose button
        logger.info("Opening Moodle file picker...")
        choose_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".fp-btn-choose")))
        driver.execute_script("arguments[0].click();", choose_btn)
        
        # Wait for dialog to open
        time.sleep(2)
        
        # Ensure we are on the "Subir un archivo" (Upload a file) tab
        try:
            upload_tab = driver.find_element(By.XPATH, "//a[contains(., 'Subir un archivo') or contains(., 'Upload a file')]")
            driver.execute_script("arguments[0].click();", upload_tab)
            time.sleep(1)
        except NoSuchElementException:
            pass
            
        # Find the actual file input in the dialog
        file_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file'][name='repo_upload_file']")))
        
        # Unhide if necessary
        driver.execute_script("arguments[0].style.display = 'block';", file_input)
        
        # Send keys to the input
        logger.info("Uploading XML file...")
        file_input.send_keys(os.path.abspath(xml_path))
        time.sleep(1)
        
        # Click "Subir este archivo" (Upload this file)
        logger.info("Clicking upload button in dialog...")
        upload_btn = wait.until(EC.presence_of_element_located((By.XPATH, "//button[contains(@class, 'fp-upload-btn')] | //button[contains(text(), 'Subir este archivo')]")))
        driver.execute_script("arguments[0].click();", upload_btn)
        
        # Wait for the file to upload and dialog to close
        time.sleep(4)
        
        # Submit the import
        logger.info("Submitting glosario import form...")
        submit_import_btn = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#id_submitbutton, input[type='submit']")))
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", submit_import_btn)
        time.sleep(1)
        driver.execute_script("arguments[0].click();", submit_import_btn)
        time.sleep(3)
        
        # Check for Moodle import result messages
        try:
            result_elements = driver.find_elements(By.CSS_SELECTOR, ".box.generalbox p, .notifyproblem, .notifysuccess, .alert")
            for res in result_elements:
                text = res.text.strip()
                if text:
                    logger.info(f"Moodle import result: {text}")
        except Exception:
            pass
            
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
