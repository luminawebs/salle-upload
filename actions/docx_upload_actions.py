import os
import re
import time
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from actions.moodle_actions import navigate_to_course
from core.wysiwyg_handler import inject_html_into_wysiwyg, extract_html_from_wysiwyg
from config.settingsSALLE import ConfigSALLE as Config

logger = logging.getLogger(__name__)

def parse_activity_number(val):
    if val.isdigit(): return int(val)
    roman = {'i':1,'v':5,'x':10,'l':50,'c':100,'d':500,'m':1000}
    res = 0; val = val.lower()
    for i in range(len(val)):
        if i + 1 < len(val) and roman.get(val[i], 0) < roman.get(val[i+1], 0):
            res -= roman.get(val[i], 0)
        else:
            res += roman.get(val[i], 0)
    return res

def click_edit_for_activity(driver, activity_name_prefix, wait_time):
    """
    Finds an activity by prefix name and clicks 'Editar ajustes'.
    """
    wait = WebDriverWait(driver, wait_time)
    if "course/view.php" not in driver.current_url:
        from actions.moodle_actions import navigate_to_course
        from config.settingsSALLE import ConfigSALLE as Config
        # Extract course ID from URL if possible or assume it's the current one... 
        # Better yet, pass course_id into click_edit_for_activity
        pass # We'll handle this in the main loop instead
        
    # Attempt to expand all sections if they are collapsed (Moodle 4.x)
    try:
        expand_all_btn = driver.find_elements(By.CSS_SELECTOR, "[data-action='toggleall'], .section-collapse-all, .toggle-all")
        for btn in expand_all_btn:
            if btn.is_displayed() and "expand" in btn.get_attribute("aria-expanded") == "false" or "true" not in str(btn.get_attribute("aria-expanded")):
                try:
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(1)
                except:
                    pass
    except:
        pass
        
    def find_target_in_current_dom():
        activities = driver.find_elements(By.CSS_SELECTOR, "li.activity")
        for activity in activities:
            try:
                name_el = activity.find_element(By.CSS_SELECTOR, ".instancename")
                raw_text = name_el.text.strip() if name_el.text else name_el.get_attribute("innerText")
                if raw_text:
                    normalized_name = " ".join(raw_text.split()).lower()
                    normalized_search = " ".join(activity_name_prefix.split()).lower()
                    
                    if normalized_search in normalized_name:
                        return activity
                    else:
                        search_match = re.search(r'^actividad\s+([\divxlcdm]+)', normalized_search)
                        name_match = re.search(r'^actividad\s+([\divxlcdm]+)', normalized_name)
                        if search_match and name_match:
                            search_val = parse_activity_number(search_match.group(1))
                            name_val = parse_activity_number(name_match.group(1))
                            if search_val is not None and search_val == name_val:
                                return activity
            except NoSuchElementException:
                continue
        return None
        
    target_activity = find_target_in_current_dom()
    
    if not target_activity:
        body = driver.find_element(By.TAG_NAME, "body")
        if "format-buttons" in (body.get_attribute("class") or ""):
            logger.info("Activity not found immediately in Buttons format. Scanning all sections...")
            buttons = driver.find_elements(By.CSS_SELECTOR, "ul.buttons li, .buttonbox a, .sectionbutton")
            for button in buttons:
                if not button.is_displayed(): continue
                try:
                    driver.execute_script("arguments[0].click();", button)
                    time.sleep(1)
                    target_activity = find_target_in_current_dom()
                    if target_activity:
                        logger.info("Activity found after scanning buttons.")
                        break
                except:
                    pass
            
    if not target_activity:
        logger.error(f"Activity matching '{activity_name_prefix}' not found.")
        return False
        
    try:
        # Click the action menu toggle
        dropdown_toggle = target_activity.find_element(By.CSS_SELECTOR, "a.dropdown-toggle[title='Editar'], a[aria-label='Editar'], a[data-toggle='dropdown']")
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", dropdown_toggle)
        time.sleep(0.5)
        
        try:
            wait.until(EC.element_to_be_clickable(dropdown_toggle)).click()
        except:
            driver.execute_script("arguments[0].click();", dropdown_toggle)
            
        time.sleep(1)
        
        # Click 'Editar ajustes'
        edit_option_xpath = ".//a[contains(@class, 'dropdown-item') and (contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'editar ajustes') or contains(@href, 'modedit.php'))]"
        edit_settings_option = wait.until(lambda d: target_activity.find_element(By.XPATH, edit_option_xpath))
        
        try:
            edit_settings_option.click()
        except:
            driver.execute_script("arguments[0].click();", edit_settings_option)
            
        return True
    except Exception as e:
        logger.error(f"Failed to click edit for '{activity_name_prefix}': {e}")
        return False

def upload_introduccion_general(driver, html_path, wait_time):
    wait = WebDriverWait(driver, wait_time)
    
    # The Introduccion General is inside a label that contains "-- Inicio texto presentación --"
    # Wait, the label itself doesn't have an instancename.
    def find_target_label():
        activities = driver.find_elements(By.CSS_SELECTOR, "li.activity.label, li.activity.text")
        for activity in activities:
            if "Inicio texto presentac" in activity.get_attribute("innerHTML") or "Inicio texto presentac" in activity.text:
                return activity
        return None
        
    target_label = find_target_label()
    
    if not target_label:
        body = driver.find_element(By.TAG_NAME, "body")
        if "format-buttons" in (body.get_attribute("class") or ""):
            logger.info("Introduccion General not found immediately in Buttons format. Scanning all sections...")
            buttons = driver.find_elements(By.CSS_SELECTOR, "ul.buttons li, .buttonbox a, .sectionbutton")
            for button in buttons:
                if not button.is_displayed(): continue
                try:
                    driver.execute_script("arguments[0].click();", button)
                    time.sleep(1)
                    target_label = find_target_label()
                    if target_label:
                        break
                except:
                    pass
            
    if not target_label:
        logger.error("Could not find the label containing the Introducción General accordion.")
        return False
        
    try:
        dropdown_toggle = target_label.find_element(By.CSS_SELECTOR, "a.dropdown-toggle[title='Editar'], a[aria-label='Editar'], a[data-toggle='dropdown']")
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", dropdown_toggle)
        time.sleep(0.5)
        try:
            wait.until(EC.element_to_be_clickable(dropdown_toggle)).click()
        except:
            driver.execute_script("arguments[0].click();", dropdown_toggle)
        time.sleep(1)
        
        edit_option_xpath = ".//a[contains(@class, 'dropdown-item') and (contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'editar ajustes') or contains(@href, 'modedit.php'))]"
        edit_settings = wait.until(lambda d: target_label.find_element(By.XPATH, edit_option_xpath))
        try:
            edit_settings.click()
        except:
            driver.execute_script("arguments[0].click();", edit_settings)
            
        # Wait for editor to load
        submit_btn_css = "#id_submitbutton, #id_submitbutton2, input[name='submitbutton'], input[name='submitbutton2'], button[name='submitbutton']"
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, submit_btn_css)))
        
        # Wait for editor to fully load (either TinyMCE iframe or Atto content box)
        try:
            editor_ready_css = ".tox-edit-area__iframe, .editor_atto_content, textarea[name='introeditor[text]']"
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, editor_ready_css)))
            time.sleep(1) # Extra buffer for tinymce content to populate
        except Exception:
            pass
            
        # Extract HTML
        current_html = ""
        for _ in range(5):
            current_html = extract_html_from_wysiwyg(driver, target_section="descripcion")
            if current_html and len(current_html.strip()) > 0:
                break
            time.sleep(1)
            
        if not current_html:
            logger.error("Failed to extract current HTML from the Introducción General label.")
            return False
            
        with open(html_path, 'r', encoding='utf-8') as f:
            new_intro_html = f.read()
            
        # Regex replacement between markers
        # We look for the closing </p> after the start marker and the opening <p before the end marker
        pattern = r'(-- Inicio texto presentaci[oó]n --.*?<\/span><\/p>)(.*?)(<p[^>]*><span[^>]*>-- Fin texto de presentaci[oó]n --)'
        
        def repl(m):
            return m.group(1) + "\n" + new_intro_html + "\n" + m.group(3)
            
        if re.search(pattern, current_html, re.IGNORECASE | re.DOTALL):
            updated_html = re.sub(pattern, repl, current_html, flags=re.IGNORECASE | re.DOTALL)
            success = inject_html_into_wysiwyg(driver, updated_html, wait_time, target_section="descripcion")
            if success:
                logger.info("Successfully updated Introducción General.")
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "body.path-course-view")))
                return True
        else:
            logger.error("Regex markers for Introducción General not found in current HTML.")
            # Fallback cancel
            cancel_btn = driver.find_element(By.CSS_SELECTOR, "input[name='cancel'], button[name='cancel'], #id_cancel")
            driver.execute_script("arguments[0].click();", cancel_btn)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "body.path-course-view")))
            return False
            
    except Exception as e:
        logger.error(f"Error uploading Introducción General: {e}")
        return False


def disable_multimedia_filter_for_activity(driver, activity_name_prefix, wait_time):
    """
    Navigates to an activity, goes to 'Más > Filtros', 
    and sets 'Complementos multimedia' to 'Desconectado'.
    """
    wait = WebDriverWait(driver, wait_time)
    
    # 1. Find the activity on the course page
    activities = driver.find_elements(By.CSS_SELECTOR, "li.activity")
    target_activity = None
    
    for activity in activities:
        try:
            name_el = activity.find_element(By.CSS_SELECTOR, ".instancename")
            raw_text = name_el.text.strip() if name_el.text else name_el.get_attribute("innerText")
            if raw_text:
                normalized_name = " ".join(raw_text.split()).lower()
                normalized_search = " ".join(activity_name_prefix.split()).lower()
                if normalized_search in normalized_name:
                    target_activity = activity
                    break
                else:
                    # Fallback for Actividad X matching Actividad Roman_X
                    search_match = re.search(r'^actividad\s+([\divxlcdm]+)', normalized_search)
                    name_match = re.search(r'^actividad\s+([\divxlcdm]+)', normalized_name)
                    if search_match and name_match:
                        search_val = parse_activity_number(search_match.group(1))
                        name_val = parse_activity_number(name_match.group(1))
                        if search_val is not None and search_val == name_val:
                            target_activity = activity
                            break
        except NoSuchElementException:
            continue
            
    if not target_activity:
        logger.error(f"Activity '{activity_name_prefix}' not found for configuring filters.")
        return False
        
    try:
        # Click the activity main link to enter it
        activity_link = target_activity.find_element(By.CSS_SELECTOR, "a")
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", activity_link)
        time.sleep(0.5)
        
        try:
            activity_link.click()
        except:
            driver.execute_script("arguments[0].click();", activity_link)
            
        # Wait until we are on the activity view page (no longer on course view)
        wait.until(lambda d: "course/view.php" not in d.current_url)
        time.sleep(1)
        
        # 2. Click 'Más' if it's a dropdown, then click 'Filtros'
        try:
            # Look for the 'Filtros' link
            filtros_xpath = "//a[contains(@href, 'filter/manage.php') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'filtros')]"
            
            # Moodle 4.x has tertiary nav. The 'Filtros' might be hidden under 'Más'
            mas_dropdowns = driver.find_elements(By.XPATH, "//a[contains(@class, 'dropdown-toggle') and contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'más')]")
            if mas_dropdowns:
                for mas in mas_dropdowns:
                    if mas.is_displayed():
                        driver.execute_script("arguments[0].click();", mas)
                        time.sleep(0.5)
                        break
                        
            filtros_link = wait.until(EC.presence_of_element_located((By.XPATH, filtros_xpath)))
            driver.execute_script("arguments[0].click();", filtros_link)
        except Exception as e:
            logger.error(f"Could not find 'Filtros' menu: {e}")
            return False
            
        # 3. Wait for Filters page to load
        wait.until(lambda d: "filter/manage.php" in d.current_url)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "select[name='mediaplugin'], select.menumediaplugin, #menumediaplugin")))
        
        # 4. Select 'Desconectado' (-1)
        from selenium.webdriver.support.ui import Select
        select_el = driver.find_element(By.CSS_SELECTOR, "select[name='mediaplugin'], select.menumediaplugin, #menumediaplugin")
        select = Select(select_el)
        select.select_by_value("-1")
        
        # 5. Click Save Changes
        try:
            save_btn = driver.find_element(By.CSS_SELECTOR, "input[type='submit'], button[type='submit']")
            driver.execute_script("arguments[0].click();", save_btn)
            wait.until(EC.staleness_of(save_btn))
            time.sleep(1)
        except:
            logger.warning("No submit button found on filters page. It might be auto-saving.")
            time.sleep(1)
            
        logger.info(f"Successfully disabled multimedia filter for {activity_name_prefix}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to disable multimedia filter for '{activity_name_prefix}': {e}")
        return False

def run_docx_upload_workflow(driver, course_id: int, wait_time: int = 10):
    base_dir = os.path.join("assets", str(course_id))
    actividades_dir = os.path.join(base_dir, "actividades")
    material_dir = os.path.join(base_dir, "material")
    introduccion_dir = os.path.join(base_dir, "introduccion")
    
    if not navigate_to_course(driver, Config.MOODLE_URL, course_id, wait_time):
        return
        
    # Upload Introduccion General
    intro_path = os.path.join(introduccion_dir, "introduccion_general.html")
    if os.path.exists(intro_path):
        if "course/view.php" not in driver.current_url:
            navigate_to_course(driver, Config.MOODLE_URL, course_id, wait_time)
            
        logger.info(f"Uploading Introducción General for course {course_id}...")
        upload_introduccion_general(driver, intro_path, wait_time)
        time.sleep(2)
        
    # Upload Actividades
    if os.path.exists(actividades_dir):
        for filename in sorted(os.listdir(actividades_dir)):
            if filename.endswith(".html") and filename.startswith("actividad"):
                if "course/view.php" not in driver.current_url:
                    navigate_to_course(driver, Config.MOODLE_URL, course_id, wait_time)
                    
                # extract number, e.g. actividad1.html -> 1
                match = re.search(r'\d+', filename)
                if match:
                    act_num = match.group()
                    activity_prefix = f"ACTIVIDAD {act_num}"
                    logger.info(f"Uploading {filename} to {activity_prefix}...")
                    
                    if click_edit_for_activity(driver, activity_prefix, wait_time):
                        wait = WebDriverWait(driver, wait_time)
                        submit_btn_css = "#id_submitbutton, #id_submitbutton2, input[name='submitbutton'], input[name='submitbutton2'], button[name='submitbutton']"
                        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, submit_btn_css)))
                        
                        file_path = os.path.join(actividades_dir, filename)
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            
                        # Transform the HTML
                        from actions.html_transformer import transform_activity_html, extract_questions_from_html_to_gift, remove_questions_from_html
                        
                        gift_txt_path = os.path.join(actividades_dir, f"{activity_prefix}_questions.txt")
                        questions_extracted = False
                        
                        if extract_questions_from_html_to_gift(content, gift_txt_path):
                            content = remove_questions_from_html(content)
                        
                        content = transform_activity_html(content, course_id)
                            
                        # Use descripcion for tasks
                        success = inject_html_into_wysiwyg(driver, content, wait_time, target_section="descripcion")
                        if success:
                            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "body.path-course-view")))
                            logger.info(f"Success: {filename}")
                            
                            # Navigate to filters and configure
                            disable_multimedia_filter_for_activity(driver, activity_prefix, wait_time)
                            
                            # Navigate back to course view
                            if "course/view.php" not in driver.current_url:
                                navigate_to_course(driver, Config.MOODLE_URL, course_id, wait_time)
                        else:
                            logger.error(f"Failed to inject {filename}")
                    time.sleep(2)

    # Upload Material de referencia
    if os.path.exists(material_dir):
        for filename in sorted(os.listdir(material_dir)):
            if filename.endswith(".html") and filename.startswith("Material_de_referencia_U"):
                if "course/view.php" not in driver.current_url:
                    navigate_to_course(driver, Config.MOODLE_URL, course_id, wait_time)
                    
                match = re.search(r'U(\d+)', filename)
                if match:
                    u_num = match.group(1)
                    material_prefix = f"Material de referencia Unidad {u_num}"
                    logger.info(f"Uploading {filename} to {material_prefix}...")
                    
                    if click_edit_for_activity(driver, material_prefix, wait_time):
                        wait = WebDriverWait(driver, wait_time)
                        submit_btn_css = "#id_submitbutton, #id_submitbutton2, input[name='submitbutton'], input[name='submitbutton2'], button[name='submitbutton']"
                        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, submit_btn_css)))
                        
                        file_path = os.path.join(material_dir, filename)
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            
                        # Use contenido for Pages
                        success = inject_html_into_wysiwyg(driver, content, wait_time, target_section="contenido")
                        if success:
                            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "body.path-course-view")))
                            logger.info(f"Success: {filename}")
                        else:
                            logger.error(f"Failed to inject {filename}")
                    time.sleep(2)
