import os
import re
import time
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from config.settingsSALLE import ConfigSALLE as Config
from actions.moodle_actions import navigate_to_course
from actions.html_transformer import extract_questions_from_html_to_gift
from actions.puntos_extras_actions import _get_cmid_for_activity
from actions.cuestionario_grade_actions import update_quiz_grades

logger = logging.getLogger(__name__)

def import_gift_to_cuestionario(driver, course_id: int, activity_name_prefix: str, txt_path: str, wait_time: int) -> bool:
    wait = WebDriverWait(driver, wait_time)
    
    navigate_to_course(driver, Config.MOODLE_URL, course_id, wait_time)
    cmid = _get_cmid_for_activity(driver, activity_name_prefix, wait_time)
    if not cmid:
        return False
        
    import_url = f"{Config.MOODLE_URL}/question/bank/importquestions/import.php?cmid={cmid}"
    driver.get(import_url)
    
    try:
        logger.info(f"[{activity_name_prefix}] Step 1: Navigating to import page...")
        format_gift_radio = wait.until(EC.presence_of_element_located((By.ID, "id_format_gift")))
        if not format_gift_radio.is_selected():
            driver.execute_script("arguments[0].click();", format_gift_radio)
            
        logger.info(f"[{activity_name_prefix}] Step 2: Expanding 'General' section...")
        general_header = driver.find_elements(By.XPATH, "//a[contains(text(), 'General')]")
        if general_header:
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", general_header[0])
            time.sleep(0.5)
            if "true" not in str(general_header[0].get_attribute("aria-expanded")).lower():
                driver.execute_script("arguments[0].click();", general_header[0])
                time.sleep(0.5)
                
        logger.info(f"[{activity_name_prefix}] Step 3: Selecting correct category...")
        category_select = wait.until(EC.presence_of_element_located((By.ID, "id_category")))
        from selenium.webdriver.support.ui import Select
        sel = Select(category_select)
        
        search_txt = f"por defecto en {activity_name_prefix}".lower()
        found_option = False
        
        logger.info(f"[{activity_name_prefix}] Searching for category: '{search_txt}'")
        
        # First try to match "por defecto en {prefix}"
        for opt in sel.options:
            raw_text = opt.get_attribute("textContent") or ""
            opt_text = " ".join(raw_text.split()).lower()
            if search_txt in opt_text:
                try:
                    sel.select_by_value(opt.get_attribute("value"))
                except:
                    driver.execute_script("arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('change', {bubbles: true}));", category_select, opt.get_attribute("value"))
                found_option = True
                break
                
        # Fallback: try to just match the prefix
        if not found_option:
            fallback_search = activity_name_prefix.lower()
            logger.info(f"[{activity_name_prefix}] Fallback searching for: '{fallback_search}'")
            for opt in sel.options:
                raw_text = opt.get_attribute("textContent") or ""
                opt_text = " ".join(raw_text.split()).lower()
                if fallback_search in opt_text:
                    try:
                        sel.select_by_value(opt.get_attribute("value"))
                    except:
                        driver.execute_script("arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('change', {bubbles: true}));", category_select, opt.get_attribute("value"))
                    found_option = True
                    break
                    
        if not found_option:
            logger.warning(f"[{activity_name_prefix}] Category not found in import dropdown. Using default.")
            
        logger.info(f"[{activity_name_prefix}] Step 4a: Opening file picker...")
        choose_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[contains(@value, 'Seleccione un archivo')] | //button[contains(text(), 'Seleccione un archivo')] | //*[contains(text(), 'Choose a file')] | //button[contains(text(), 'Seleccione un archivo...')]")))
        driver.execute_script("arguments[0].click();", choose_btn)
        time.sleep(1)
        
        logger.info(f"[{activity_name_prefix}] Step 4b: Selecting 'Subir un archivo' tab...")
        try:
            upload_menu = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Subir un archivo') or contains(text(), 'Upload a file')]")))
            driver.execute_script("arguments[0].click();", upload_menu)
            time.sleep(1)
        except:
            pass # Might already be selected
            
        logger.info(f"[{activity_name_prefix}] Step 4c: Choosing file...")
        file_input = wait.until(EC.presence_of_element_located((By.NAME, "repo_upload_file")))
        file_input.send_keys(os.path.abspath(txt_path))
        time.sleep(1)
        
        logger.info(f"[{activity_name_prefix}] Step 4d: Clicking 'Subir este archivo' in modal...")
        upload_this_file_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'subir este archivo') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'upload this file')]")))
        driver.execute_script("arguments[0].click();", upload_this_file_btn)
        
        # Wait for modal to disappear
        wait.until(EC.invisibility_of_element_located((By.XPATH, "//div[contains(@class, 'moodle-dialogue-base')]")))
        time.sleep(1)
        
        logger.info(f"[{activity_name_prefix}] Step 5: Submitting import...")
        submit_btn = wait.until(EC.element_to_be_clickable((By.ID, "id_submitbutton")))
        driver.execute_script("arguments[0].click();", submit_btn)
        
        logger.info(f"[{activity_name_prefix}] Step 6: Clicking continue on import summary...")
        continue_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'continuar') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'continue')]")))
        driver.execute_script("arguments[0].click();", continue_btn)
        
        logger.info(f"Successfully imported GIFT file for {activity_name_prefix}.")
        return True
    except Exception as e:
        logger.error(f"Failed to import GIFT file for {activity_name_prefix}: {e}")
        return False

def add_questions_to_cuestionario(driver, course_id: int, activity_name_prefix: str, question_count: int, wait_time: int) -> bool:
    wait = WebDriverWait(driver, wait_time)
    
    current_url = driver.current_url or ""
    cmid = None
    if "cmid=" in current_url:
        import urllib.parse
        parsed = urllib.parse.urlparse(current_url)
        qs = urllib.parse.parse_qs(parsed.query)
        if 'cmid' in qs:
            cmid = qs['cmid'][0]

    if not cmid:
        navigate_to_course(driver, Config.MOODLE_URL, course_id, wait_time)
        cmid = _get_cmid_for_activity(driver, activity_name_prefix, wait_time)
        
    if not cmid:
        logger.error(f"Could not find cmid for {activity_name_prefix}")
        return False
        
    try:
        logger.info(f"[{activity_name_prefix}] Navigating to quiz to find 'Preguntas' tab...")
        quiz_url = f"{Config.MOODLE_URL}/mod/quiz/view.php?id={cmid}"
        driver.get(quiz_url)
        time.sleep(1.5)
        
        # Click the "Preguntas" tab specifically
        preguntas_tab = driver.find_elements(By.XPATH, "//ul[contains(@class, 'nav-tabs')]//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'preguntas')]")
        if preguntas_tab:
            driver.execute_script("arguments[0].click();", preguntas_tab[0])
            logger.info(f"[{activity_name_prefix}] Clicked 'Preguntas' tab.")
            time.sleep(2)
        else:
            logger.warning(f"[{activity_name_prefix}] Could not find 'Preguntas' tab. Attempting direct URL navigation.")
            edit_quiz_url = f"{Config.MOODLE_URL}/mod/quiz/edit.php?cmid={cmid}"
            driver.get(edit_quiz_url)
            time.sleep(2)
    except Exception as e:
        logger.error(f"[{activity_name_prefix}] Error navigating to Preguntas tab: {e}")
        edit_quiz_url = f"{Config.MOODLE_URL}/mod/quiz/edit.php?cmid={cmid}"
        driver.get(edit_quiz_url)
        time.sleep(2)
    
    try:
        logger.info(f"[{activity_name_prefix}] Checking for existing questions...")
        existing_questions = driver.find_elements(By.CSS_SELECTOR, "li.slot")
        if len(existing_questions) > 0:
            logger.info(f"[{activity_name_prefix}] Already contains {len(existing_questions)} questions. Skipping addition.")
            return True
            
        logger.info(f"[{activity_name_prefix}] Finding 'Agregar' menu...")
        add_menus = driver.find_elements(By.CSS_SELECTOR, "span.add-menu-outer a[data-toggle='dropdown']")
        if not add_menus:
            add_menus = driver.find_elements(By.CSS_SELECTOR, "div.add-menu-outer a[data-action='addmenu']")
        if not add_menus:
            add_menus = driver.find_elements(By.XPATH, "//a[contains(., 'Agregar') or contains(., 'Add')]")
            
        if add_menus:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", add_menus[-1])
            time.sleep(0.5)
            try:
                add_menus[-1].click()
            except:
                driver.execute_script("arguments[0].click();", add_menus[-1])
            time.sleep(1)
            
            logger.info(f"[{activity_name_prefix}] Opening 'pregunta aleatoria' modal...")
            # Find the 'una pregunta aleatoria' button
            random_btns = driver.find_elements(By.XPATH, "//a[contains(@data-action, 'addarandomquestion') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'una pregunta aleatoria')]")
            visible_random_btn = None
            for btn in random_btns[::-1]: # Search backwards to get the one for the last menu
                if btn.is_displayed():
                    visible_random_btn = btn
                    break
            
            if visible_random_btn:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", visible_random_btn)
                time.sleep(0.5)
                try:
                    visible_random_btn.click()
                except:
                    driver.execute_script("arguments[0].click();", visible_random_btn)
            else:
                logger.warning(f"[{activity_name_prefix}] Could not find visible 'una pregunta aleatoria' button.")
                return False
            time.sleep(2)
            
            logger.info(f"[{activity_name_prefix}] Searching for category in modal...")
            try:
                cat_input = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[data-fieldtype='autocomplete']")))
                driver.execute_script("arguments[0].click();", cat_input)
                time.sleep(1)
                
                suggestions = driver.find_elements(By.CSS_SELECTOR, "ul.form-autocomplete-suggestions li[role='option']")
                search_txt = f"por defecto en {activity_name_prefix}".lower()
                found = False
                for li in suggestions:
                    # Replace non-breaking spaces before matching
                    li_text = li.get_attribute("textContent").replace("\xa0", " ").strip().lower()
                    if search_txt in li_text:
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", li)
                        time.sleep(0.5)
                        try:
                            li.click()
                        except:
                            driver.execute_script("arguments[0].dispatchEvent(new MouseEvent('click', {bubbles: true}));", li)
                        found = True
                        break
                
                if not found:
                    for li in suggestions:
                        li_text = li.get_attribute("textContent").replace("\xa0", " ").strip().lower()
                        if activity_name_prefix.lower() in li_text:
                            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", li)
                            time.sleep(0.5)
                            try:
                                li.click()
                            except:
                                driver.execute_script("arguments[0].dispatchEvent(new MouseEvent('click', {bubbles: true}));", li)
                            found = True
                            break
                            
                if found:
                    time.sleep(1) # Small pause to let the dropdown close
                    logger.info(f"[{activity_name_prefix}] Clicking 'Aplicar filtros'...")
                    apply_btn = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "button[data-filteraction='apply']")))
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", apply_btn)
                    time.sleep(0.5)
                    try:
                        apply_btn.click()
                    except:
                        driver.execute_script("arguments[0].click();", apply_btn)
                            
                time.sleep(2) # Give it time to load the questions table after selecting category
                
                logger.info(f"[{activity_name_prefix}] Selecting all bank questions...")
                try:
                    select_all = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@id='qbheadercheckbox' or @id='cbqb']")))
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", select_all)
                    time.sleep(0.5)
                    if not select_all.is_selected():
                        try:
                            select_all.click()
                        except:
                            driver.execute_script("arguments[0].click();", select_all)
                except Exception as e:
                    logger.warning(f"[{activity_name_prefix}] Could not find or click 'Seleccionar todos': {e}")
                    
            except Exception as e:
                logger.warning(f"[{activity_name_prefix}] Could not select category in autocomplete: {e}")
            
            # --- NEW LOGIC: Select the number of random questions ---
            target_random_count = min(10, question_count)
            logger.info(f"[{activity_name_prefix}] Selecting {target_random_count} random questions...")
            try:
                random_select_el = wait.until(EC.visibility_of_element_located((By.ID, "menurandomcount")))
                from selenium.webdriver.support.ui import Select
                sel_random = Select(random_select_el)
                sel_random.select_by_value(str(target_random_count))
                time.sleep(0.5)
            except Exception as e:
                logger.warning(f"[{activity_name_prefix}] Could not select the number of random questions: {e}")
            
            logger.info(f"[{activity_name_prefix}] Clicking 'Agregar pregunta aleatoria'...")
            try:
                add_random_btn = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@name='addrandom'] | //button[@name='addrandom']")))
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", add_random_btn)
                time.sleep(0.5)
                try:
                    add_random_btn.click()
                except:
                    driver.execute_script("arguments[0].click();", add_random_btn)
                time.sleep(2)
            except Exception as e:
                logger.warning(f"[{activity_name_prefix}] Could not click 'Agregar pregunta aleatoria': {e}")
            
            logger.info(f"Successfully added questions and random questions to {activity_name_prefix} quiz.")
            return True
        else:
            logger.warning(f"Could not find 'Agregar' menu for {activity_name_prefix}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to add random questions to {activity_name_prefix} quiz: {e}")
        return False

def run_cuestionario_export_workflow(driver, course_id: int, wait_time: int = 10):
    logger.info(f"Starting Cuestionario Export workflow for course {course_id}...")
    base_dir = os.path.join("assets", str(course_id))
    actividades_dir = os.path.join(base_dir, "actividades")
    
    if not os.path.exists(actividades_dir):
        logger.info(f"No actividades directory found for course {course_id}.")
        return

    for filename in sorted(os.listdir(actividades_dir)):
        if filename.endswith(".html") and filename.startswith("actividad"):
            match = re.search(r'\d+', filename)
            if match:
                act_num = match.group()
                activity_prefix = f"ACTIVIDAD {act_num}"
                
                html_path = os.path.join(actividades_dir, filename)
                gift_txt_path = os.path.join(actividades_dir, f"{activity_prefix}_questions.txt")
                
                # We need to extract the questions from HTML to create the GIFT file
                with open(html_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                questions_extracted = extract_questions_from_html_to_gift(content, gift_txt_path)
                
                if questions_extracted and os.path.exists(gift_txt_path) and os.path.getsize(gift_txt_path) > 0:
                    with open(gift_txt_path, 'r', encoding='utf-8') as f:
                        gift_content = f.read()
                    q_count = len([q for q in gift_content.split('\n\n') if q.strip()])
                    export_enabled = getattr(Config, "ENABLE_CUESTIONARIO_EXPORT", False)
                    grade_update_enabled = getattr(Config, "ENABLE_CUESTIONARIO_GRADE_UPDATE", False)
                    
                    if export_enabled:
                        logger.info(f"Exporting questions for {activity_prefix}...")
                        export_success = False
                        if import_gift_to_cuestionario(driver, course_id, activity_prefix, gift_txt_path, wait_time):
                            if add_questions_to_cuestionario(driver, course_id, activity_prefix, q_count, wait_time):
                                export_success = True
                        
                        if export_success and grade_update_enabled:
                            update_quiz_grades(driver, activity_prefix, wait_time)
                        elif not grade_update_enabled:
                            logger.info(f"[{activity_prefix}] Quiz grade update skipped via config.")
                    else:
                        logger.info(f"[{activity_prefix}] Question export skipped via config.")
                        if grade_update_enabled:
                            logger.info(f"[{activity_prefix}] Navigating to update grades...")
                            navigate_to_course(driver, Config.MOODLE_URL, course_id, wait_time)
                            cmid = _get_cmid_for_activity(driver, activity_prefix, wait_time)
                            if cmid:
                                edit_quiz_url = f"{Config.MOODLE_URL}/mod/quiz/edit.php?cmid={cmid}"
                                driver.get(edit_quiz_url)
                                time.sleep(2)
                                update_quiz_grades(driver, activity_prefix, wait_time)
                            else:
                                logger.error(f"Could not find cmid for {activity_prefix} to update grades.")
