"""
competencias_actions.py
-----------------------
Automates Phase 6: Ajuste de competencias
1. Set "Completar la competencia" in Course > Competencias.
2. For specific activities, assign the correct RAC and set to "Completar la competencia".
"""

import logging
import os
import json
import time
import re

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select

from actions.moodle_actions import navigate_to_course
from config.settings import Config

logger = logging.getLogger(__name__)

def _get_cmid_for_activity(driver, activity_name: str, wait_time: int) -> str:
    """Returns the cmid (course module ID) for a given activity name on the course page."""
    wait = WebDriverWait(driver, wait_time)
    try:
        activity_links = driver.find_elements(By.CSS_SELECTOR, "a.aalink, a.instancename")
        for link in activity_links:
            text = link.text or ""
            if activity_name.lower() in text.lower():
                href = link.get_attribute("href")
                if href:
                    m = re.search(r"id=(\d+)", href)
                    if m:
                        return m.group(1)
    except Exception as e:
        logger.error(f"Error finding activity '{activity_name}': {e}")
    return None

def configure_course_competencies(driver, course_id: int, wait_time: int):
    """
    Step 1: On course, enter Competencias and set all rule outcomes to 3.
    Tries direct URL first, falls back to UI navigation.
    """
    logger.info(f"Configuring Course Competencies for {course_id}...")
    
    # Try direct URL first
    direct_url = f"{Config.MOODLE_URL}/course/competencies.php?courseid={course_id}"
    driver.get(direct_url)
    time.sleep(2)
    
    # Check if we landed on the competencies page
    if "competencies.php" not in driver.current_url:
        logger.info("Direct URL failed or redirected. Attempting UI navigation (Más > Competencias)...")
        navigate_to_course(driver, Config.MOODLE_URL, course_id, wait_time)
        
        try:
            # Click "Más"
            mas_menu = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Más') or contains(text(), 'More')]"))
            )
            driver.execute_script("arguments[0].click();", mas_menu)
            time.sleep(1)
            
            # Click "Competencias"
            comp_link = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Competencias') or contains(text(), 'Competencies')]"))
            )
            driver.execute_script("arguments[0].click();", comp_link)
            time.sleep(2)
        except Exception as e:
            logger.error(f"Failed to navigate to Competencias via UI: {e}")
            return
            
    # Now we are on the Competencias page.
    # Find all selectors: <select data-field="ruleoutcome">
    try:
        selects = driver.find_elements(By.CSS_SELECTOR, "select[data-field='ruleoutcome']")
        if not selects:
            logger.info("No ruleoutcome selectors found on the course competencies page.")
        
        for idx, select_elem in enumerate(selects):
            select_obj = Select(select_elem)
            current_val = select_elem.get_attribute("value")
            if current_val != "3":
                logger.info(f"  Setting rule outcome {idx+1}/{len(selects)} to 'Completar la competencia' (3)")
                select_obj.select_by_value("3")
                # Trigger change event in case Moodle saves via AJAX
                driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", select_elem)
                time.sleep(1)
            else:
                logger.info(f"  Rule outcome {idx+1}/{len(selects)} is already '3'.")
                
        logger.info("Course Competencies configured successfully.")
    except Exception as e:
        logger.error(f"Error configuring course competencies: {e}")


def configure_activity_competencies(driver, course_id: int, wait_time: int):
    """
    Step 2: Assign RACs to specific activities.
    """
    logger.info("Parsing contenidos.json for RAC mappings...")
    json_path = os.path.join("assets", str(course_id), "contenidos.json")
    if not os.path.exists(json_path):
        logger.error(f"contenidos.json not found for course {course_id}. Skipping activity competencies.")
        return
        
    rac_mapping = {}
    unique_racs = []
    
    with open(json_path, "r", encoding="utf-8") as f:
        contenidos_data = json.load(f)
        
    for i in range(1, 9):
        week_key = f"Semana {i}"
        week_data = contenidos_data.get(week_key, {})
        rac_str = week_data.get("rac", "").strip()
        if rac_str:
            if rac_str not in unique_racs:
                unique_racs.append(rac_str)
            
            rac_index = unique_racs.index(rac_str) + 1
            rac_mapping[i] = f"RAC {rac_index}"
            
    if not rac_mapping:
        logger.warning("No RACs found in contenidos.json. Skipping activity competencies.")
        return
        
    logger.info(f"RAC Mapping: {rac_mapping}")
    
    target_activities = []
    # SX | Actividad (For weeks 2,4,6,8)
    for i in [2, 4, 6, 8]: 
        if i in rac_mapping: target_activities.append((f"S{i} | Actividad", rac_mapping[i]))
    # SX | Foro (For weeks 3,5,7)
    for i in [3, 5, 7]: 
        if i in rac_mapping: target_activities.append((f"S{i} | Foro", rac_mapping[i]))
    # SX | Puntos extras (weeks 1-8)
    for i in range(1, 9): 
        if i in rac_mapping: target_activities.append((f"S{i} | Puntos extras", rac_mapping[i]))
    # SX | Evaluación (weeks 1-8)
    for i in range(1, 9): 
        if i in rac_mapping: target_activities.append((f"S{i} | Evaluación", rac_mapping[i]))
    # SX | Evaluación - SP (weeks 1-8)
    for i in range(1, 9): 
        if i in rac_mapping: target_activities.append((f"S{i} | Evaluación - SP", rac_mapping[i]))
    # SX | Trabajo (weeks 1-8)
    for i in range(1, 9): 
        if i in rac_mapping: target_activities.append((f"S{i} | Trabajo", rac_mapping[i]))
        
    wait = WebDriverWait(driver, wait_time)
    
    for activity_name, rac_target in target_activities:
        logger.info(f"Configuring {activity_name} -> {rac_target}")
        
        # Navigate to course to get cmid
        navigate_to_course(driver, Config.MOODLE_URL, course_id, wait_time)
        cmid = _get_cmid_for_activity(driver, activity_name, wait_time)
        
        if not cmid:
            logger.warning(f"Could not find activity '{activity_name}'. Skipping.")
            continue
            
        edit_url = f"{Config.MOODLE_URL}/course/modedit.php?update={cmid}"
        driver.get(edit_url)
        
        try:
            # Expand Competencias section robustly
            driver.execute_script("""
                var fieldset = document.getElementById('id_competenciessection');
                if (fieldset && fieldset.classList.contains('collapsed')) {
                    var link = fieldset.querySelector('a[data-toggle="collapse"]');
                    if (link) link.click();
                }
            """)
            time.sleep(1)
            
            # Check if RAC is already selected using the hidden select
            already_selected = driver.execute_script(f"""
                var targetRac = '{rac_target}';
                var select = document.getElementById('id_competencies');
                if (select) {{
                    for (var i = 0; i < select.options.length; i++) {{
                        if (select.options[i].text.includes(targetRac) && select.options[i].selected) {{
                            return true;
                        }}
                    }}
                }}
                return false;
            """)
            
            if not already_selected:
                # Open the autocomplete combobox
                driver.execute_script("""
                    var select = document.getElementById('id_competencies');
                    if (select) {
                        var container = select.closest('.fitem') || select.closest('.form-group') || document.getElementById('id_competenciessection');
                        if (container) {
                            var cb = container.querySelector('input[role="combobox"]');
                            if (cb) {
                                cb.click();
                                cb.focus();
                            }
                        }
                    }
                """)
                time.sleep(1)
                
                # Find and click the RAC suggestion
                driver.execute_script(f"""
                    var targetRac = '{rac_target}';
                    var lis = document.querySelectorAll('.form-autocomplete-suggestions li[role="option"]');
                    var clicked = false;
                    for (var i = 0; i < lis.length; i++) {{
                        var optText = lis[i].innerText || lis[i].textContent;
                        if (optText.includes(targetRac)) {{
                            var event = new MouseEvent('mousedown', {{ bubbles: true, cancelable: true, view: window }});
                            lis[i].dispatchEvent(event);
                            lis[i].click();
                            clicked = true;
                            break;
                        }}
                    }}
                    
                    if (!clicked) {{
                        // Fallback to directly selecting the hidden option
                        var select = document.getElementById('id_competencies');
                        if (select) {{
                            for (var i = 0; i < select.options.length; i++) {{
                                if (select.options[i].text.includes(targetRac)) {{
                                    select.options[i].selected = true;
                                    var event = new Event('change', {{ bubbles: true }});
                                    select.dispatchEvent(event);
                                    break;
                                }}
                            }}
                        }}
                    }}
                """)
                time.sleep(1.5)
            else:
                logger.info(f"  {rac_target} is already selected.")
                
            # Set rule outcome to 3 ("Completar la competencia")
            try:
                # Use JS to reliably change the rule select
                driver.execute_script("""
                    var select = document.getElementById('id_competency_rule');
                    if (select && select.value !== "3") {
                        select.value = "3";
                        var event = new Event('change', { bubbles: true });
                        select.dispatchEvent(event);
                    }
                """)
            except Exception as e:
                logger.warning(f"  Could not set competency_rule to 3: {e}")
                
            # Submit form
            submit_btn = wait.until(EC.element_to_be_clickable((By.ID, "id_submitbutton2"))) # Guardar cambios y regresar al curso
            driver.execute_script("arguments[0].click();", submit_btn)
            time.sleep(2)
            
            logger.info(f"Successfully configured competencies for {activity_name}")
            
        except Exception as e:
            logger.error(f"Failed to configure competencies for {activity_name}: {e}")


def run_ajuste_competencias_workflow(driver, course_id: int, wait_time: int = 10):
    """
    Main entry point for Phase 6 Ajuste de Competencias.
    """
    logger.info(f"Starting Ajuste de Competencias workflow for course {course_id}...")
    
    configure_course_competencies(driver, course_id, wait_time)
    configure_activity_competencies(driver, course_id, wait_time)
    
    logger.info("Ajuste de Competencias workflow completed.")
