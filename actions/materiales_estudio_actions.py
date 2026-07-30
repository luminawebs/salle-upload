import logging
import time
import os
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

from actions.moodle_actions import navigate_to_course
from config.settings import Config
from core.wysiwyg_handler import inject_html_into_wysiwyg
from actions.html_transformer import format_urls_in_html, format_typography_in_html

logger = logging.getLogger(__name__)

def add_etiqueta_materiales(driver, section_element, wait_time=10):
    wait = WebDriverWait(driver, wait_time)
    
    # Click 'Añadir una actividad o recurso'
    add_activity_btns = section_element.find_elements(By.CSS_SELECTOR, "button.activity-add, a.section-modchooser-link:not([data-action='addSection']), button.section-modchooser-link, [data-action='open-chooser']")
    if not add_activity_btns:
        logger.warning("Could not find 'Add activity' button.")
        return False
    add_activity_btn = add_activity_btns[-1]
    
    try:
        wait.until(EC.element_to_be_clickable(add_activity_btn)).click()
    except WebDriverException:
        driver.execute_script("arguments[0].click();", add_activity_btn)
        
    chooser = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".modchooser, .modal-dialog, .modal-content, [data-region='chooserdialogue']")))
    time.sleep(1)
    
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
        logger.warning("Could not find Label option in chooser.")
        return False
        
    try:
        wait.until(EC.presence_of_element_located((By.ID, "id_submitbutton2")))
    except:
        pass
    video_html = '<p><video class="nomediaplugin" crossorigin="anonymous" autoplay="autoplay" loop="loop" muted="true">   <source src="https://unisallevirtual.lasalle.edu.co/multimedia/etiquetas/materialesdeestudio.mp4">   Materiales de Estudio.  </video></p>'
    
    success = inject_html_into_wysiwyg(driver, video_html, wait_time, target_section="intro")
    if not success: 
        return False
    # Wait for redirect back to course view
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "body.path-course-view")))
    except:
        pass
        
    return True

def add_pagina_materiales(driver, section_element, course_id, unidad_num, wait_time=10):
    wait = WebDriverWait(driver, wait_time)
    
    # Click 'Añadir una actividad o recurso'
    add_activity_btns = section_element.find_elements(By.CSS_SELECTOR, "button.activity-add, a.section-modchooser-link:not([data-action='addSection']), button.section-modchooser-link, [data-action='open-chooser']")
    if not add_activity_btns:
        logger.warning("Could not find 'Add activity' button.")
        return False
    add_activity_btn = add_activity_btns[-1]
    
    try:
        wait.until(EC.element_to_be_clickable(add_activity_btn)).click()
    except WebDriverException:
        driver.execute_script("arguments[0].click();", add_activity_btn)
        
    chooser = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".modchooser, .modal-dialog, .modal-content, [data-region='chooserdialogue']")))
    time.sleep(1)
    
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".modchooser .option, .modchooser .modchooser-item, .modal-dialog .option, .modal-dialog .modchooser-item, [data-region='chooserdialogue'] .option")))
    except TimeoutException:
        pass

    keywords = ["page", "página", "pagina"]
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
        logger.warning("Could not find Page option in chooser.")
        return False
        
    try:
        wait.until(EC.presence_of_element_located((By.ID, "id_name")))
    except:
        pass
        
    # Set Title
    name_input = wait.until(EC.presence_of_element_located((By.ID, "id_name")))
    driver.execute_script("arguments[0].value = '';", name_input)
    name_input.send_keys(f"Lecturas complementarias unidad {unidad_num}")
    driver.execute_script("arguments[0].dispatchEvent(new Event('change', {bubbles: true}));", name_input)

    # Build Content
    video_html = '<video class="nomediaplugin" crossorigin="anonymous" autoplay="autoplay" loop="loop" muted="true">   <source src="https://unisallevirtual.lasalle.edu.co/multimedia/etiquetas/Mat_Referencia.mp4">   RPLCMNT  </video>'
    
    html_file_path = os.path.join("workspace", str(course_id), "material", f"Material_de_referencia_U{unidad_num}.html")
    file_content = ""
    if os.path.exists(html_file_path):
        with open(html_file_path, "r", encoding="utf-8") as f:
            file_content = f.read()
            
        file_content = format_urls_in_html(file_content, link_text="(Disponible aquí)")
        file_content = format_typography_in_html(file_content)
    else:
        logger.warning(f"File not found: {html_file_path}")
    
    full_content = video_html + file_content
    
    # Inject a space into Description (intro) without submitting, in case Moodle requires it
    inject_html_into_wysiwyg(driver, " ", wait_time, target_section="intro", submit_form=False)
    
    # Inject into Page content WYSIWYG without submitting
    success = inject_html_into_wysiwyg(driver, full_content, wait_time, target_section="contenido", submit_form=False)
    if not success: 
        logger.error("Failed to inject HTML into WYSIWYG")
        return False
        
    # Explicitly click "Save and return to course" (id_submitbutton2)
    try:
        submit_btn = wait.until(EC.element_to_be_clickable((By.ID, "id_submitbutton2")))
        try:
            submit_btn.click()
        except:
            driver.execute_script("arguments[0].click();", submit_btn)
            
        try:
            wait.until(EC.staleness_of(submit_btn))
        except TimeoutException:
            # Check for validation errors if it didn't submit
            errors = driver.find_elements(By.CSS_SELECTOR, ".invalid-feedback, .error, .alert-danger")
            for err in errors:
                if err.is_displayed() and err.text:
                    logger.error(f"Validation error creating Page for Unidad {unidad_num}: {err.text}")
            time.sleep(1.5)
    except Exception as e:
        logger.error(f"Could not click save button for Page Unidad {unidad_num}: {e}")

    # Wait for redirect back to course view
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "body.path-course-view")))
    except:
        pass
        
    return True

def run_materiales_estudio_workflow(driver, course_id, wait_time=10):
    logger.info(f"Starting Materiales de Estudio workflow for course {course_id}")
    
    # Ensure we are on the course homepage
    logger.info("Navigating to course homepage to find sections...")
    navigate_to_course(driver, ConfigSALLE.MOODLE_URL, course_id, wait_time)
    time.sleep(2)
    
    unidad_num = 1
    while True:
        logger.info(f"Processing Unidad {unidad_num}")
        
        # Navigate to course homepage at the start of each iteration to ensure all sections are visible
        navigate_to_course(driver, ConfigSALLE.MOODLE_URL, course_id, wait_time)
        time.sleep(2)
        
        try:
            sections = driver.find_elements(By.CSS_SELECTOR, "li.section")
            logger.info(f"Found {len(sections)} sections on the page.")
            target_section = None
            for sec in sections:
                try:
                    title_elem = sec.find_element(By.CSS_SELECTOR, ".sectionname, h3.sectionname, h4")
                    if f"UNIDAD {unidad_num}" in title_elem.text.upper():
                        target_section = sec
                        break
                except:
                    if f"UNIDAD {unidad_num}" in sec.text.upper():
                        target_section = sec
                        break
                    
            if not target_section:
                logger.warning(f"Could NOT find any section containing the text 'UNIDAD {unidad_num}'. Stopping unit iteration.")
                break
                
            logger.info(f"Successfully found section for Unidad {unidad_num}. Adding 'Área de texto y medios' (Etiqueta)...")
            add_etiqueta_materiales(driver, target_section, wait_time)
            time.sleep(2)
            
            # Find section again
            sections = driver.find_elements(By.CSS_SELECTOR, "li.section")
            for sec in sections:
                try:
                    title_elem = sec.find_element(By.CSS_SELECTOR, ".sectionname, h3.sectionname, h4")
                    if f"UNIDAD {unidad_num}" in title_elem.text.upper():
                        target_section = sec
                        break
                except:
                    if f"UNIDAD {unidad_num}" in sec.text.upper():
                        target_section = sec
                        break
                        
            logger.info(f"Successfully added Etiqueta. Now adding 'Página' for Unidad {unidad_num}...")
            add_pagina_materiales(driver, target_section, course_id, unidad_num, wait_time)
            time.sleep(2)
            
        except Exception as e:
            logger.error(f"Error processing Unidad {unidad_num}: {e}")
            break
            
        unidad_num += 1
            
    logger.info("Finished Materiales de Estudio workflow")
