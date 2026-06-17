import os
import logging
import time
import re
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

logger = logging.getLogger(__name__)

def parse_raw_document(filepath):
    """
    Parses the raw_docx_extracted.html file and extracts the course structure.
    Returns a list of sections, where each section has a list of activities.
    
    Structure format:
    [
        {
            "unit_number": 0,
            "section_name": "Bienvenidos al curso",
            "activities": [
                {"name": "Avisos", "type": "Foro"},
                {"name": "Foro permanente de dudas", "type": "Foro"},
                {"name": "Encuentros virtuales", "type": "Herramienta externa"}
            ]
        },
        ...
    ]
    """
    sections = [
        {
            "unit_number": 0,
            "section_name": "Bienvenidos al curso",
            "activities": [
                {"name": "Avisos", "type": "Foro"},
                {"name": "Foro permanente de dudas", "type": "Foro"},
                {"name": "Encuentros virtuales", "type": "Herramienta externa"}
            ]
        },
        {
            "unit_number": 1,
            "section_name": "GENERALIDADES DEL CURSO",
            "activities": [
                {"name": "Introducción General", "type": "Área de texto y medios"}
            ]
        }
    ]

    if not os.path.exists(filepath):
        logger.error(f"Raw document not found: {filepath}")
        return sections

    with open(filepath, "r", encoding="utf-8") as f:
        html_content = f.read()

    soup = BeautifulSoup(html_content, "html.parser")
    
    current_section = None
    current_activity = None
    
    for element in soup.find_all(['p', 'ul', 'ol', 'h1', 'h2', 'h3']):
        text = element.get_text().strip()
        
        # Detect Section (Unidad)
        if 'UNIDAD DIDÁCTICA' in text.upper():
            m = re.search(r'UNIDAD DIDÁCTICA\s*(\d+)', text.upper())
            if m:
                unit_num_original = int(m.group(1))
                name_part = text[m.end():].strip(' :.-')
                if not name_part:
                    nxt = element.find_next_sibling('p')
                    if nxt:
                        name_part = nxt.get_text().strip()
                full_name = f'UNIDAD {unit_num_original}. {name_part}'
                
                # section-0=Bienvenidos, section-1=Generalidades, section-2=Unidad 1
                moodle_section_idx = unit_num_original + 1
                
                current_section = {
                    "unit_number": moodle_section_idx,
                    "section_name": full_name,
                    "activities": []
                }
                sections.append(current_section)
                current_activity = None
                
        # Detect Activity
        elif "ACTIVIDAD" in text.upper():
            if current_section is not None:
                m = re.match(r'^ACTIVIDAD\s*\d+\s*:', text.upper())
                if m or text.upper().startswith("ACTIVIDAD"):
                    current_activity = {
                        "name": text,
                        "type": None
                    }
                    current_section["activities"].append(current_activity)
                    
        # Detect Activity Type
        elif element.name in ['ul', 'ol'] and current_activity is not None:
            list_text = text.lower()
            if "foro" in list_text or "tarea" in list_text or "cuestionario" in list_text:
                for li in element.find_all('li'):
                    li_text = li.get_text().lower()
                    if 'x' in li_text:
                        if 'foro' in li_text:
                            current_activity["type"] = "Foro"
                            break
                        elif 'tarea' in li_text:
                            current_activity["type"] = "Tarea"
                            break
                        elif 'cuestionario' in li_text:
                            current_activity["type"] = "Cuestionario"
                            break

    return sections


def check_and_create_sections(driver, required_sections_count, wait_time=10):
    wait = WebDriverWait(driver, wait_time)
    try:
        sections = driver.find_elements(By.CSS_SELECTOR, "li.section, li.course-section")
        current_count = len(sections)
        logger.info(f"Found {current_count} existing sections. Required: {required_sections_count}")
        
        if current_count < required_sections_count:
            needed = required_sections_count - current_count
            logger.info(f"Need to create {needed} new sections.")
            
            for _ in range(needed):
                try:
                    add_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-action='addSection'], .changenumsections a, .add-sections, .add-section, a.add-section")))
                    try:
                        add_btn.click()
                    except:
                        driver.execute_script("arguments[0].click();", add_btn)
                    time.sleep(2)
                except Exception as e:
                    logger.error(f"Failed to click 'Add section' button: {e}")
                    break
        else:
            logger.info("Enough sections already exist.")
        return True
    except Exception as e:
        logger.error(f"Error checking/creating sections: {e}")
        return False


def rename_section_by_element(driver, section_element, new_name, wait_time=10):
    wait = WebDriverWait(driver, wait_time)
    from selenium.webdriver.common.keys import Keys
    try:
        try:
            current_name_element = section_element.find_element(By.CSS_SELECTOR, ".sectionname, h3.sectionname, h3, h4, a.course-section-header")
        except:
            current_name_element = section_element
            
        if new_name.lower() in current_name_element.text.lower():
            return True
            
        edit_icon = section_element.find_element(By.CSS_SELECTOR, ".quickediticon, [data-action='edittitle'], .edit-icon, i.fa-pen, i.fa-pencil")
        try:
            wait.until(EC.element_to_be_clickable(edit_icon)).click()
        except WebDriverException:
            driver.execute_script("arguments[0].click();", edit_icon)
            
        input_field = wait.until(lambda d: section_element.find_element(By.CSS_SELECTOR, "input[type='text']:not(.hidden), input.inplaceeditable"))
        wait.until(EC.visibility_of(input_field))
        
        input_field.send_keys(Keys.CONTROL + "a")
        input_field.send_keys(Keys.DELETE)
        input_field.send_keys(new_name)
        input_field.send_keys(Keys.RETURN)
        
        time.sleep(1)
        return True
    except Exception as e:
        logger.error(f"Failed to rename section: {e}")
        return False


def get_existing_activities(section_element):
    activities = []
    try:
        activity_elements = section_element.find_elements(By.CSS_SELECTOR, ".activity-name-area, .instancename")
        for el in activity_elements:
            text = el.text.strip().split('\n')[0]
            if text:
                activities.append(text)
    except:
        pass
    return activities


def create_activity(driver, section_element, activity_info, wait_time=10, course_id=None):
    wait = WebDriverWait(driver, wait_time)
    act_name = activity_info["name"]
    act_type = activity_info["type"]
    
    if not act_type:
        logger.warning(f"Skipping '{act_name}' due to unknown type.")
        return False
        
    logger.info(f"Creating activity: '{act_name}' of type '{act_type}'")
    
    try:
        add_activity_btns = section_element.find_elements(By.CSS_SELECTOR, "button.activity-add, a.section-modchooser-link")
        if not add_activity_btns:
            logger.error("Could not find 'Add activity' button in this section.")
            return False
            
        add_activity_btn = add_activity_btns[-1] # ALWAYS click the LAST one to append to the bottom!
        
        try:
            wait.until(EC.element_to_be_clickable(add_activity_btn)).click()
        except WebDriverException:
            driver.execute_script("arguments[0].click();", add_activity_btn)
            
        chooser = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".modchooser")))
        time.sleep(1) # Wait for AJAX/JS to populate the options
        
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".modchooser .option, .modchooser .modchooser-item")))
        except TimeoutException:
            pass
            
        type_mapping = {
            "Foro": ["forum", "foro"],
            "Tarea": ["assign", "tarea"],
            "Cuestionario": ["quiz", "cuestionario"],
            "Herramienta externa": ["lti", "external tool", "herramienta externa"],
            "Área de texto y medios": ["label", "etiqueta", "área de texto y medios", "texto y medios"]
        }
        
        keywords = type_mapping.get(act_type, [act_type.lower()])
        
        found = False
        options = chooser.find_elements(By.CSS_SELECTOR, ".option a, .option button, .option label, .modchooser-item")
        found_options_debug = []
        for option in options:
            text = option.text.lower()
            href = option.get_attribute("href") or ""
            data_name = option.get_attribute("data-name") or ""
            
            found_options_debug.append(f"text='{text}', href='{href}', data-name='{data_name}'")
            
            if any(k in text for k in keywords) or any(k in href for k in keywords) or any(k in data_name.lower() for k in keywords):
                if href and "javascript" not in href.lower():
                    logger.info(f"Navigating directly to activity creator URL: {href}")
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
            logger.error(f"Could not find activity type '{act_type}' in the chooser. Searched keywords: {keywords}")
            # Log the first 10 options to see what we are getting
            logger.debug(f"Available options in chooser: {found_options_debug[:10]}")
            try:
                chooser.find_element(By.CSS_SELECTOR, ".close, button[data-action='hide']").click()
            except:
                pass
            return False
            
        if act_type in ["Área de texto y medios", "Etiqueta", "Label"]:
            # Labels don't have a 'name' input, they just have the introeditor
            from core.wysiwyg_handler import inject_html_into_wysiwyg
            # Wait for editor to appear
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".tox-edit-area__iframe, .editor_atto_content, textarea[name='introeditor[text]']")))
                time.sleep(1)
                
                html_markers = "<p><span>-- Inicio texto presentación --</span></p><p><span>-- Fin texto de presentación --</span></p>"
                template_path = os.path.join("assets", "example_course", "GENERALIDADES DEL CURSO.html")
                course_dir = os.path.join("assets", str(course_id)) if course_id else "assets"
                extracted_path = os.path.join(course_dir, "raw_docx_extracted.html")
                if os.path.exists(template_path) and os.path.exists(extracted_path):
                    from actions.html_transformer import generate_dynamic_generalidades_html
                    try:
                        html_markers = generate_dynamic_generalidades_html(extracted_path, template_path)
                    except Exception as e:
                        logger.error(f"Error generating dynamic generalidades: {e}")
                        with open(template_path, "r", encoding="utf-8") as f:
                            html_markers = f.read()
                elif os.path.exists(template_path):
                    with open(template_path, "r", encoding="utf-8") as f:
                        html_markers = f.read()
                        
                # Fix Moodle "File does not exist" error caused by leftover draftfile.php URLs
                # Extract filename and try to embed it as Base64 like html_transformer does
                import re
                from actions.html_transformer import get_image_base64
                
                def replace_draft_image_tag(match):
                    full_tag = match.group(0)
                    src_match = re.search(r'src=["\']([^"\']*)["\']', full_tag)
                    if not src_match:
                        return full_tag
                        
                    full_url = src_match.group(1)
                    filename = full_url.split('/')[-1].split('?')[0].split('#')[0]
                    
                    if filename.lower() in ["profesor.jpg", "docente.jpg"] and course_id:
                        raw_doc_path = os.path.join("assets", str(course_id), "raw_docx_extracted.html")
                        if os.path.exists(raw_doc_path):
                            from bs4 import BeautifulSoup
                            with open(raw_doc_path, "r", encoding="utf-8") as rf:
                                raw_soup = BeautifulSoup(rf.read(), "html.parser")
                                for td in raw_soup.find_all("td"):
                                    if "Foto del perfil" in td.get_text():
                                        next_td = td.find_next_sibling("td")
                                        if next_td:
                                            img = next_td.find("img")
                                            if img and img.has_attr("src"):
                                                docx_img_src = img["src"]
                                                docx_img_path = os.path.join("assets", str(course_id), docx_img_src)
                                                if os.path.exists(docx_img_path):
                                                    import base64
                                                    with open(docx_img_path, "rb") as img_file:
                                                        encoded_string = base64.b64encode(img_file.read()).decode('utf-8')
                                                    ext = os.path.splitext(docx_img_path)[1].lower().replace('.', '')
                                                    mime_type = f"image/{ext}" if ext in ['png', 'jpg', 'jpeg', 'gif'] else "image/png"
                                                    new_src = f"data:{mime_type};base64,{encoded_string}"
                                                    return full_tag.replace(full_url, new_src)
                                                    
                    base64_data = get_image_base64(filename)
                    if base64_data:
                        return full_tag.replace(full_url, base64_data)
                    
                    logger.warning(f"Imagen del Docente no encontrada ({filename}). No se agregará imagen en Generalidades.")
                    return ""

                html_markers = re.sub(
                    r'<img[^>]*src=["\'][^"\']*draftfile\.php[^"\']*["\'][^>]*>', 
                    replace_draft_image_tag, 
                    html_markers,
                    flags=re.IGNORECASE
                )
                        
                inject_html_into_wysiwyg(driver, html_markers, wait_time, target_section="intro")
            except Exception as e:
                logger.error(f"Failed to inject markers for Label: {e}")
        else:
            name_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='name'], #id_name")))
            name_input.send_keys(act_name)
            
            # Remove the checks on habilitar, on all actividades
            try:
                from actions.actividad_actions import _configure_actividad_availability, _configure_actividad_grading
                _configure_actividad_availability(driver)
                _configure_actividad_grading(driver)
            except Exception as e:
                logger.warning(f"Could not configure availability and grading for {act_name}: {e}")
        
        submit_btn = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='submitbutton2'], #id_submitbutton2")))
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", submit_btn)
        time.sleep(1) # Give Moodle's JS a moment to initialize the form
        
        try:
            wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[name='submitbutton2'], #id_submitbutton2"))).click()
        except WebDriverException:
            driver.execute_script("arguments[0].click();", submit_btn)
            
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "body.path-course-view")))
        except TimeoutException:
            # Maybe it saved but took too long, or there's a validation error.
            # Let's check if we're still on the modedit page.
            if "modedit.php" in driver.current_url:
                logger.error(f"Failed to save '{act_name}': Form validation error or Moodle is too slow.")
                raise Exception("Save button clicked but did not navigate back to course.")
            
        logger.info(f"Successfully created '{act_name}'.")
        return True
        
    except Exception as e:
        logger.error(f"Failed to create activity '{act_name}': {e}")
        return False


def run_course_structure_creation_workflow(driver, course_id, wait_time=10):
    logger.info(f"--- Executing Course Structure Creation Workflow for Course {course_id} ---")
    
    raw_doc_path = os.path.join("assets", str(course_id), "raw_docx_extracted.html")
    sections = parse_raw_document(raw_doc_path)
    
    if not sections:
        logger.warning(f"No sections found in {raw_doc_path} or file missing.")
        return
        
    required_sections_count = len(sections)
    logger.info(f"Workflow requires {required_sections_count} sections.")
    
    check_and_create_sections(driver, required_sections_count, wait_time)
    
    wait = WebDriverWait(driver, wait_time)
    
    for section_info in sections:
        unit_num = section_info["unit_number"]
        sec_name = section_info["section_name"]
        activities = section_info["activities"]
        
        try:
            xpath_sec = f"//li[contains(@class, 'section') and (@id='section-{unit_num}' or @data-section='{unit_num}' or @data-number='{unit_num}')]"
            section_element = wait.until(EC.presence_of_element_located((By.XPATH, xpath_sec)))
            
            rename_section_by_element(driver, section_element, sec_name, wait_time)
            time.sleep(1)
            
            section_element = wait.until(EC.presence_of_element_located((By.XPATH, xpath_sec)))
            
        except TimeoutException:
            logger.error(f"Could not find section-{unit_num} on the page. Skipping.")
            continue
            
        existing_acts = get_existing_activities(section_element)
        
        for act in activities:
            exists = any(act["name"].lower() in e_act.lower() for e_act in existing_acts)
            
            if exists:
                logger.info(f"Activity '{act['name']}' already exists in {sec_name}. Skipping.")
            else:
                create_activity(driver, section_element, act, wait_time, course_id)
                try:
                    xpath_sec = f"//li[contains(@class, 'section') and (@id='section-{unit_num}' or @data-section='{unit_num}' or @data-number='{unit_num}')]"
                    section_element = wait.until(EC.presence_of_element_located((By.XPATH, xpath_sec)))
                    existing_acts = get_existing_activities(section_element)
                except TimeoutException:
                    logger.error("Lost track of section after creating activity. Stopping current section processing.")
                    break
                    
    logger.info("--- Course Structure Creation Workflow Complete ---")
