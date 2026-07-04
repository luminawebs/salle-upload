import time
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

from core.wysiwyg_handler import inject_html_into_wysiwyg

logger = logging.getLogger(__name__)

def add_etiqueta_actividades_to_section(driver, section_element, wait_time=10):
    """
    Clicks 'Añadir una actividad o recurso', selects 'Área de texto y medios' (label),
    and injects a video tag if it doesn't already exist.
    """
    wait = WebDriverWait(driver, wait_time)
    
    # 1. Check if the video already exists in this section
    try:
        existing = section_element.find_elements(By.CSS_SELECTOR, "video source[src*='actividadaprendizaje.mp4']")
        if existing:
            logger.info("  'Actividades de aprendizaje' video label already exists in this section. Skipping.")
            return True
    except Exception as e:
        logger.warning(f"  Could not check for existing video label: {e}")

    logger.info("  Adding 'Actividades de aprendizaje' video label to section...")

    # 2. Click 'Añadir una actividad o recurso'
    try:
        add_activity_btns = section_element.find_elements(By.CSS_SELECTOR, "button.activity-add, a.section-modchooser-link:not([data-action='addSection']), button.section-modchooser-link, [data-action='open-chooser']")
        if not add_activity_btns:
            logger.error("  Could not find 'Add activity' button in this section.")
            return False
            
        add_activity_btn = add_activity_btns[-1]
        
        try:
            wait.until(EC.element_to_be_clickable(add_activity_btn)).click()
        except WebDriverException:
            driver.execute_script("arguments[0].click();", add_activity_btn)
            
        # 3. Wait for chooser and select 'Área de texto y medios'
        chooser_selector = ".modchooser, .modal-dialog, .modal-content, [data-region='chooserdialogue']"
        chooser = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, chooser_selector)))
        time.sleep(1) # Wait for JS to populate
        
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".modchooser .option, .modchooser .modchooser-item, .modal-dialog .option, .modal-dialog .modchooser-item, [data-region='chooserdialogue'] .option")))
        except TimeoutException:
            pass
            
        keywords = ["label", "etiqueta", "área de texto y medios", "texto y medios", "area de texto y medios"]
        options = chooser.find_elements(By.CSS_SELECTOR, ".option a, .option button, .option label, .modchooser-item, .option")
        
        found = False
        for option in options:
            text = option.text.lower()
            href = option.get_attribute("href") or ""
            data_name = option.get_attribute("data-name") or ""
            
            if any(k in text for k in keywords) or any(k in href for k in keywords) or any(k in data_name.lower() for k in keywords):
                if href and "javascript" not in href.lower():
                    driver.get(href)
                    found = True
                    break
                else:
                    try:
                        option.click()
                        found = True
                        break
                    except WebDriverException:
                        driver.execute_script("arguments[0].click();", option)
                        found = True
                        break
                        
        if not found:
            logger.error("  Could not find 'Área de texto y medios' option in chooser.")
            # Try to close modal
            try:
                close_btn = driver.find_element(By.CSS_SELECTOR, "[data-action='close']")
                driver.execute_script("arguments[0].click();", close_btn)
            except:
                pass
            return False

        # 4. Wait for page to load
        try:
            wait.until(EC.presence_of_element_located((By.ID, "id_submitbutton2")))
        except:
            pass
            
        # 5. Inject HTML
        video_html = '<video class="nomediaplugin" crossorigin="anonymous" autoplay="autoplay" loop="loop" muted="true"><source src="https://unisallevirtual.lasalle.edu.co/multimedia/etiquetas/actividadaprendizaje.mp4">Actividades de aprendizaje.</video>'
        success = inject_html_into_wysiwyg(driver, video_html, wait_time, target_section="intro")
        
        if not success:
            logger.error("  Failed to inject video HTML into WYSIWYG.")
            return False
            
        # 6. Save and return to course
        save_btn = driver.find_element(By.CSS_SELECTOR, "#id_submitbutton2, input[name='submitbutton2'], button[name='submitbutton2']")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", save_btn)
        time.sleep(0.5)
        
        try:
            save_btn.click()
        except:
            driver.execute_script("arguments[0].click();", save_btn)
            
        # Wait for redirect back to course view
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "body.path-course-view")))
        except:
            # Check if still on edit page due to validation
            if "modedit.php" in driver.current_url:
                logger.error("  Failed to save video label: Form validation error.")
                return False
                
        logger.info("  Successfully added video label.")
        return True
        
    except Exception as e:
        logger.error(f"  Exception while adding video label: {e}")
        return False
