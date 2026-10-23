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
from core.activity_selection import get_skipped_activities
from config.settings import Config

from core import progress

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

# Example activities a course shell can come with ("ACTIVIDAD 1. XXX"): never
# the activity a document's content belongs to.
_PLACEHOLDER_NAME_RE = re.compile(r'\bx{3,}\b', re.IGNORECASE)
_LEADING_ACTIVITY_RE = re.compile(r'^\s*actividad\s+([\divxlcdm]+)\b', re.IGNORECASE)


def choose_activity(names: list, search: str):
    """
    Index of the activity on the course page that `search` ("ACTIVIDAD 1")
    means, or None. A course shell can already have example activities
    ("ACTIVIDAD 1. XXX") listed before the ones the structure step creates,
    and taking the first name that merely contained "actividad 1" put
    descriptions and rubrics in those (and "Actividad 1" also matched
    "Actividad 10"). So: same activity number at the start of the name, never
    a placeholder; other searches ("Material de referencia…") by containment.
    """
    def norm(text):
        return " ".join((text or "").split()).lower()

    wanted = _LEADING_ACTIVITY_RE.match(norm(search))
    wanted_number = parse_activity_number(wanted.group(1)) if wanted else None
    fallback = None
    for i, name in enumerate(names):
        if not name or _PLACEHOLDER_NAME_RE.search(name):
            continue
        if wanted_number is not None:
            found = _LEADING_ACTIVITY_RE.match(norm(name))
            if found and parse_activity_number(found.group(1)) == wanted_number:
                return i
        elif norm(search) in norm(name) and fallback is None:
            fallback = i
    return fallback


def _activity_names(driver):
    """(activity elements, their names) on the course page, in page order."""
    activities, names = [], []
    for activity in driver.find_elements(By.CSS_SELECTOR, "li.activity"):
        try:
            name_el = activity.find_element(By.CSS_SELECTOR, ".instancename")
        except NoSuchElementException:
            continue
        activities.append(activity)
        names.append((name_el.text.strip() if name_el.text else name_el.get_attribute("innerText")) or "")
    return activities, names


def get_edit_url_for_activity(driver, activity_name_prefix, wait_time):
    """
    Finds an activity by prefix name and clicks 'Editar ajustes'.
    """
    wait = WebDriverWait(driver, wait_time)
    if "course/view.php" not in driver.current_url:
        from actions.moodle_actions import navigate_to_course
        from config.settings import Config
        # Extract course ID from URL if possible or assume it's the current one... 
        # Better yet, pass course_id into get_edit_url_for_activity
        pass # We'll handle this in the main loop instead
        
    # Attempt to expand all sections if they are collapsed (Moodle 4.x)
    try:
        expand_all_btn = driver.find_elements(By.CSS_SELECTOR, "[data-action='toggleall'], .section-collapse-all, .toggle-all")
        for btn in expand_all_btn:
            if btn.is_displayed() and "expand" in btn.get_attribute("aria-expanded") == "false" or "true" not in str(btn.get_attribute("aria-expanded")):
                try:
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(1)
                except Exception:
                    pass
    except Exception:
        pass
        
    def find_target_in_current_dom():
        activities, names = _activity_names(driver)
        index = choose_activity(names, activity_name_prefix)
        if index is not None:
            return activities[index]
        # Fallback for "Material de referencia" which might be named "Material de estudio" etc.
        normalized_search = " ".join(activity_name_prefix.split()).lower()
        u_match = re.search(r'unidad\s+(\d+)', normalized_search)
        if "material de" in normalized_search and u_match:
            for activity, name in zip(activities, names):
                normalized_name = " ".join((name or "").split()).lower()
                if "material" in normalized_name and f"unidad {u_match.group(1)}" in normalized_name:
                    return activity
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
                except Exception:
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
        except Exception:
            driver.execute_script("arguments[0].click();", dropdown_toggle)
            
        time.sleep(1)
        
        
        # Click 'Editar ajustes'
        edit_option_xpath = ".//a[contains(@class, 'dropdown-item') and (contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'editar ajustes') or contains(@href, 'modedit.php'))]"
        edit_settings_option = wait.until(lambda d: target_activity.find_element(By.XPATH, edit_option_xpath))
        
        href = edit_settings_option.get_attribute('href')
        if not href:
            # Try to get it from onclick or similar if href is missing, but usually it's in href
            logger.error(f"Found edit option for '{activity_name_prefix}' but it has no href.")
            return None
            
        return href
    except Exception as e:
        logger.error(f"Failed to extract edit URL for '{activity_name_prefix}': {e}")
        return None

def get_edit_url_for_introduccion_general(driver, wait_time):
    wait = WebDriverWait(driver, wait_time)
    
    # The Introduccion General is inside a label that contains "-- Inicio texto presentación --"
    # Wait, the label itself doesn't have an instancename.
    def find_target_label():
        activities = driver.find_elements(By.CSS_SELECTOR, "li.activity.label, li.activity.text")
        for activity in activities:
            html = activity.get_attribute("innerHTML").lower()
            text = activity.text.lower()
            if ("inicio texto presentaci" in html or 
                "inicio texto presentaci" in text or 
                "presentación del espacio" in html or 
                "presentacion del espacio" in html or 
                "generalidades del curso" in html or
                "introducción general" in html or
                "introduccion general" in html):
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
                except Exception:
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
        except Exception:
            driver.execute_script("arguments[0].click();", dropdown_toggle)
        time.sleep(1)
        
        edit_option_xpath = ".//a[contains(@class, 'dropdown-item') and (contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'editar ajustes') or contains(@href, 'modedit.php'))]"
        edit_settings = wait.until(lambda d: target_label.find_element(By.XPATH, edit_option_xpath))
        
        href = edit_settings.get_attribute('href')
        if not href:
            logger.error("Found edit option for Introducción General but it has no href.")
            return None
        return href
        
    except Exception as e:
        logger.error(f"Error finding Introducción General edit URL: {e}")
        return None

def upload_introduccion_general_to_editor(driver, html_path, wait_time):
    wait = WebDriverWait(driver, wait_time)
    try:
            
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
        # We look for the closing </p> after the start marker and the opening <p before the end marker.
        # This regex is robust against missing <span> tags or extra whitespace.
        pattern = r'(--\s*Inicio texto presentaci[oó]n\s*--.*?<\/p>)(.*?)(<p[^>]*>.*?--\s*Fin texto de presentaci[oó]n\s*--)'
        
        def repl(m):
            return m.group(1) + "\n" + new_intro_html + "\n" + m.group(3)
            
        if re.search(pattern, current_html, re.IGNORECASE | re.DOTALL):
            updated_html = re.sub(pattern, repl, current_html, flags=re.IGNORECASE | re.DOTALL)
            success = inject_html_into_wysiwyg(driver, updated_html, wait_time, target_section="descripcion")
            if success:
                logger.info("Successfully updated Introducción General.")
                return True
        else:
            logger.error("Regex markers for Introducción General not found in current HTML.")
            # Log the first 500 characters of the HTML to help debug
            logger.debug(f"Current HTML preview: {current_html[:500]}...")
            # Fallback cancel
            try:
                cancel_btn = driver.find_element(By.CSS_SELECTOR, "input[name='cancel'], button[name='cancel'], #id_cancel")
                driver.execute_script("arguments[0].click();", cancel_btn)
            except Exception:
                pass
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
    activities, names = _activity_names(driver)
    index = choose_activity(names, activity_name_prefix)
    target_activity = activities[index] if index is not None else None

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
        except Exception:
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
            # We use XPath to specifically find the save button and avoid matching header search buttons
            save_xpath = "//input[@name='savechanges' or contains(translate(@value, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'guardar') or contains(translate(@value, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'save')]"
            save_btn = wait.until(EC.presence_of_element_located((By.XPATH, save_xpath)))
            
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", save_btn)
            time.sleep(0.5)
            
            try:
                wait.until(EC.element_to_be_clickable((By.XPATH, save_xpath))).click()
            except Exception:
                driver.execute_script("arguments[0].click();", save_btn)
                
            try:
                wait.until(EC.staleness_of(save_btn))
            except Exception:
                pass
            time.sleep(1)
        except Exception as e:
            logger.warning(f"Could not find or click save button on filters page: {e}")
            time.sleep(1)
            
        logger.info(f"Successfully disabled multimedia filter for {activity_name_prefix}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to disable multimedia filter for '{activity_name_prefix}': {e}")
        return False

_MEDIA_SELECT_CSS = "select[name='mediaplugin'], select.menumediaplugin, #menumediaplugin"
_FILTER_SAVE_XPATH = "//input[@name='savechanges' or contains(translate(@value, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'guardar') or contains(translate(@value, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'save')]"
_CONTEXT_ID_JS = "return (window.M && M.cfg && M.cfg.contextid) || null;"
# Picks "Desconectado" (-1); false when the select has no such option.
_SELECT_OFF_JS = (
    "var s = arguments[0];"
    "for (var i = 0; i < s.options.length; i++) {"
    "  if (s.options[i].value === '-1') {"
    "    s.value = '-1'; s.dispatchEvent(new Event('change', {bubbles: true})); return true;"
    "  }"
    "}"
    "return false;"
)
_CLICK_JS = "arguments[0].click();"


def _course_context_id(driver):
    """The course's context id, from the course page (M.cfg, else its 'Más > Filtros' link)."""
    try:
        context_id = driver.execute_script(_CONTEXT_ID_JS)
    except Exception:
        context_id = None
    if context_id:
        return str(context_id)
    for link in driver.find_elements(By.CSS_SELECTOR, "a[href*='filter/manage.php']"):
        found = re.search(r"contextid=(\d+)", link.get_attribute("href") or "")
        if found:
            return found.group(1)
    return None


def _media_filter_select(driver, wait):
    """The 'Complementos multimedia' select on a filters page, or None."""
    try:
        return wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, _MEDIA_SELECT_CSS)))
    except TimeoutException:
        return None


def disable_multimedia_filter_for_course(driver, course_id, wait_time):
    """
    Sets 'Complementos multimedia' to 'Desconectado' once for the whole course
    (course 'Más > Filtros'), so every activity and page in it inherits it —
    instead of once per activity. Saves, reloads the page and only returns
    True when the select reads 'Desconectado' again. False (with a warning)
    when it can't be done, e.g. the filter is locked or off at site level:
    the caller then disables it per activity, as before.
    """
    wait = WebDriverWait(driver, wait_time)

    def failed(reason):
        logger.warning(
            f"No se pudo desconectar 'Complementos multimedia' a nivel de curso ({reason}). "
            "Se desconectará en cada actividad y en cada página de Lecturas complementarias."
        )
        return False

    try:
        if not navigate_to_course(driver, Config.MOODLE_URL, course_id, wait_time):
            return failed("no se pudo abrir el curso")
        context_id = _course_context_id(driver)
        if not context_id:
            return failed("no se encontró el contexto del curso")
        filters_url = f"{Config.MOODLE_URL.rstrip('/')}/filter/manage.php?contextid={context_id}"
        logger.info(f"Abriendo los filtros del curso: {filters_url}")

        driver.get(filters_url)
        select_el = _media_filter_select(driver, wait)
        if select_el is None:
            return failed("la fila 'Complementos multimedia' no aparece en Filtros; puede estar bloqueada o apagada para todo el sitio")
        if not select_el.is_enabled():
            return failed("la opción 'Complementos multimedia' está bloqueada")
        if not driver.execute_script(_SELECT_OFF_JS, select_el):
            return failed("la opción 'Desconectado' no está disponible")

        save_btn = wait.until(EC.presence_of_element_located((By.XPATH, _FILTER_SAVE_XPATH)))
        driver.execute_script(_CLICK_JS, save_btn)
        try:
            wait.until(EC.staleness_of(save_btn))
        except TimeoutException:
            pass
        time.sleep(1)

        # Verify: reload and read the saved value back.
        driver.get(filters_url)
        select_el = _media_filter_select(driver, wait)
        value = select_el.get_attribute("value") if select_el is not None else None
        if value != "-1":
            return failed(f"después de guardar, el valor no quedó en 'Desconectado' (valor leído: {value!r})")

        logger.info("Complementos multimedia desconectado a nivel de curso (verificado tras recargar).")
        progress.ok("Complementos multimedia desconectados en todo el curso")
        return True
    except Exception as e:
        return failed(f"error: {e}")


def upload_activity_fragment(driver, course_id, file_path: str, activity_prefix: str, wait_time: int, activity_type: str = None,
                             disable_filter: bool = True):
    """
    Uploads one activity fragment (an HTML file written by the splitter) into
    the description of the Moodle activity whose name matches activity_prefix,
    then sets forum completion and disables the multimedia filter (unless
    disable_filter is False: the course already has it off).

    activity_type ("Cuestionario", "Tarea", …): read from the fragment's own
    "Herramientas … marque con una X" row when not given. For a Cuestionario
    every question is removed from the description, so students never see
    the questions — or which option is correct — before taking the quiz.
    """
    filename = os.path.basename(file_path)
    edit_url = get_edit_url_for_activity(driver, activity_prefix, wait_time)
    if edit_url:
        original_window = driver.current_window_handle
        driver.execute_script(f"window.open('{edit_url}', '_blank');")
        driver.switch_to.window(driver.window_handles[-1])
        
        try:
            wait = WebDriverWait(driver, wait_time)
            submit_btn_css = "#id_submitbutton, #id_submitbutton2, input[name='submitbutton'], input[name='submitbutton2'], button[name='submitbutton']"
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, submit_btn_css)))
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Transform the HTML
            from actions.html_transformer import transform_activity_html, remove_questions_from_html
            
            if activity_type is None:
                from bs4 import BeautifulSoup
                from core.data_parser import activity_type_for
                activity_type = activity_type_for(course_id, file_path, content)
            original = content
            content = remove_questions_from_html(content, is_quiz=(activity_type == "Cuestionario"))
            if activity_type == "Cuestionario":
                # Also the questions only the AI found (see core/ai_question_review.py).
                from core.ai_question_review import strip_accepted_questions
                content = strip_accepted_questions(course_id, filename, original, content)
            content = transform_activity_html(content, course_id)
                
            is_forum = False
            try:
                body = driver.find_element(By.TAG_NAME, "body")
                if "path-mod-forum" in (body.get_attribute("class") or ""):
                    is_forum = True
            except Exception:
                pass

            submit = not (is_forum and getattr(Config, "ENABLE_FORO_ACTIVITY_COMPLETION_UPDATE", True))

            # Use descripcion for tasks
            success = inject_html_into_wysiwyg(driver, content, wait_time, target_section="descripcion", submit_form=submit)
            if success:
                if not submit:
                    # Do Foro Completion Logic
                    try:
                        # Expand "Condiciones de finalización de actividad"
                        try:
                            container = driver.find_element(By.ID, "id_activitycompletionheadercontainer")
                            if not container.is_displayed():
                                header = driver.find_element(By.CSS_SELECTOR, "a[aria-controls='id_activitycompletionheadercontainer']")
                                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", header)
                                time.sleep(0.5)
                                driver.execute_script("arguments[0].click();", header)
                                time.sleep(1)
                        except Exception:
                            pass
                            
                        # Select "Añadir requisitos"
                        req_radio = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='radio'][name='completion'][value='2']")))
                        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", req_radio)
                        time.sleep(0.5)
                        if not req_radio.is_selected():
                            driver.execute_script("arguments[0].click();", req_radio)
                            time.sleep(1)
                            
                        # Select "Recibir una calificación"
                        grade_check = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='checkbox'][name='completionusegrade']")))
                        if not grade_check.is_selected():
                            driver.execute_script("arguments[0].click();", grade_check)
                            time.sleep(1)
                            
                        # Select "Foro completo" from dropdown
                        from selenium.webdriver.support.ui import Select
                        grade_item = driver.find_element(By.ID, "id_completiongradeitemnumber")
                        Select(grade_item).select_by_value("1")
                        time.sleep(0.5)
                    except Exception as e:
                        logger.warning(f"Could not configure Foro completion for {filename}: {e}")
                        
                    # Click Save since we deferred it
                    try:
                        submit_btn = driver.find_element(By.CSS_SELECTOR, "#id_submitbutton, #id_submitbutton2, input[name='submitbutton2'], input[name='submitbutton']")
                        try:
                            submit_btn.click()
                        except Exception:
                            driver.execute_script("arguments[0].click();", submit_btn)
                    except Exception as e:
                        logger.error(f"Failed to submit form for {filename}: {e}")

                # Wait until we are redirected back to the course view (or whatever page) in the new tab
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "body.path-course-view")))
                logger.info(f"Success: {filename}")
                progress.ok(f"Descripción subida: {activity_prefix}")
                
                # Navigate to filters and configure (it will do this inside the new tab!)
                if disable_filter:
                    disable_multimedia_filter_for_activity(driver, activity_prefix, wait_time)
            else:
                logger.error(f"Failed to inject {filename}")
            time.sleep(2)
        finally:
            driver.close()
            driver.switch_to.window(original_window)


def run_docx_upload_workflow(driver, course_id: int, wait_time: int = 10, per_activity_filter: bool = True):
    """per_activity_filter False: the course already has 'Complementos multimedia' off (see disable_multimedia_filter_for_course)."""
    base_dir = os.path.join("workspace", str(course_id))
    actividades_dir = os.path.join(base_dir, "actividades")
    material_dir = os.path.join(base_dir, "material")
    introduccion_dir = os.path.join(base_dir, "introduccion")
    
    if not navigate_to_course(driver, Config.MOODLE_URL, course_id, wait_time):
        return
        
    # Upload Introduccion General
    intro_path = os.path.join(introduccion_dir, "introduccion_general.html")
    if getattr(Config, "ENABLE_GENERALIDADES_ACCORDION_UPLOAD", False):
        # The Generalidades accordion step already put the introduction in that
        # label (renamed "Presentación"); uploading the plain version here would
        # replace the accordion — and the label is no longer found by its old text.
        logger.info("Introducción General: ya se subió como acordeón de Generalidades; no se sube la versión simple.")
    elif os.path.exists(intro_path):
        logger.info(f"Uploading Introducción General for course {course_id}...")
        edit_url = get_edit_url_for_introduccion_general(driver, wait_time)
        if edit_url:
            original_window = driver.current_window_handle
            driver.execute_script(f"window.open('{edit_url}', '_blank');")
            driver.switch_to.window(driver.window_handles[-1])
            try:
                upload_introduccion_general_to_editor(driver, intro_path, wait_time)
                time.sleep(2)
            finally:
                driver.close()
                driver.switch_to.window(original_window)
        else:
            logger.error("Could not extract edit URL for Introducción General.")
        
    # Upload Actividades
    skipped_activities = get_skipped_activities(course_id)
    if os.path.exists(actividades_dir):
        for filename in sorted(os.listdir(actividades_dir)):
            if filename.endswith(".html") and filename.startswith("actividad"):

                # extract number, e.g. actividad1.html -> 1
                match = re.search(r'\d+', filename)
                if match:
                    act_num = match.group()
                    if act_num in skipped_activities:
                        logger.info(f"Actividad {act_num} excluida por el usuario — omitiendo subida de {filename}.")
                        continue
                    activity_prefix = f"ACTIVIDAD {act_num}"
                    logger.info(f"Uploading {filename} to {activity_prefix}...")
                    
                    upload_activity_fragment(driver, course_id, os.path.join(actividades_dir, filename), activity_prefix, wait_time,
                                             disable_filter=per_activity_filter)

    # Activities the user added in the review panel: matched by their name
    # (the document heading the structure step created them with).
    from core.document_corrections import get_extra_activities, EXTRA_DIR
    for extra in get_extra_activities(course_id):
        logger.info(f"Uploading {extra['archivo']} to '{extra['nombre']}' (añadida en la revisión)...")
        upload_activity_fragment(driver, course_id, os.path.join(base_dir, EXTRA_DIR, extra["archivo"]), extra["nombre"], wait_time,
                                 activity_type=extra["tipo"], disable_filter=per_activity_filter)

