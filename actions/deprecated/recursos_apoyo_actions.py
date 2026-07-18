import logging
import os
import json
import re
import time
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.support.ui import Select

from actions.moodle_actions import navigate_to_course
from config.settings import Config

logger = logging.getLogger(__name__)

def extract_reference_data(text):
    """
    Parses a reference string and extracts the Concepto (Title), 
    the rest of the reference (without URL), and the URL.
    Returns: (concepto, citation_text, url)
    """
    # Remove prefix like "Recurso 1: " or "Recurso 2:" or "Recurso2:"
    clean_text = re.sub(r'(?i)^(Recurso\s*\d+:\s*)', '', text).strip()
    
    # Extract URL (robustly handle newlines or spaces around it if needed)
    url_match = re.search(r'(https?://[^\s]+)', clean_text)
    url = url_match.group(1) if url_match else "#"
    
    # Extract Title (Concepto) using robust regex
    concepto = ""
    # Matches (YYYY). or (YYYY, Month DD). then grabs everything up to [ or (ed.) or . [A-Z] or end of string or http
    title_match = re.search(r'\(\d{4}[^\)]*\)\.\s*(.+?)(?:\s*\[|\s*\(ed\.\)|\.\s*[A-Z]|\.\s*$|https?://)', clean_text)
    if title_match:
        concepto = title_match.group(1).strip()
        if concepto.endswith('.'):
            concepto = concepto[:-1]
    else:
        # Fallback for references without a standard (YYYY). date format
        text_before_url = clean_text.split('http')[0].strip()
        if '. ' in text_before_url:
            concepto = text_before_url.split('. ')[0].strip()
        else:
            # Take up to first 100 chars
            concepto = text_before_url[:100].strip()
            
    if not concepto:
        concepto = "Recurso de apoyo"
            
    # The citation text for the HTML template is everything except the URL
    citation_text = clean_text
    if url != "#":
        citation_text = citation_text.replace(url, '').strip()
        
    return concepto, citation_text, url

def get_unidad_for_week(week_num):
    if week_num in [1, 2]: return "Unidad 1"
    if week_num in [3, 4, 5]: return "Unidad 2"
    if week_num in [6, 7, 8]: return "Unidad 3"
    return "Unidad 1"


def _extract_items_from_html(html_text):
    if not html_text or not isinstance(html_text, str):
        return []

    soup = BeautifulSoup(html_text, "html.parser")
    items = []

    for tag in soup.find_all(["p", "li"]):
        if tag.find_parent(["p", "li"]):
            continue

        normalized_text = " ".join(tag.get_text(" ", strip=True).split())
        if not normalized_text:
            continue

        items.append(str(tag))

    if items:
        return items

    fallback_text = " ".join(soup.get_text(" ", strip=True).split())
    return [fallback_text] if fallback_text else []


def _normalize_actualidad_items(actualidad_data):
    if not actualidad_data:
        return []

    if isinstance(actualidad_data, list):
        return [item for item in actualidad_data if item is not None]

    if isinstance(actualidad_data, dict):
        if 'items' in actualidad_data and isinstance(actualidad_data['items'], list):
            return [item for item in actualidad_data['items'] if item is not None]

        if 'html_content' in actualidad_data and isinstance(actualidad_data['html_content'], str):
            return _extract_items_from_html(actualidad_data['html_content'])

        items = []
        for value in actualidad_data.values():
            if isinstance(value, list):
                items.extend([item for item in value if item is not None])
            elif isinstance(value, str):
                items.extend(_extract_items_from_html(value))
        return items

    return [str(actualidad_data)]


def _inject_italic_concept(soup, paragraph, concepto, citation_text):
    """
    Renders citation text with the concept in italics:
    - If concepto is found in citation_text, italicize the first match.
    - If not found, prepend <i>concepto</i>. before the citation.
    """
    paragraph.clear()
    citation_text = citation_text or ""
    concepto = (concepto or "").strip()

    if not concepto:
        paragraph.string = citation_text
        return

    match = re.search(re.escape(concepto), citation_text, flags=re.IGNORECASE)
    if match:
        before = citation_text[:match.start()]
        matched_text = citation_text[match.start():match.end()]
        after = citation_text[match.end():]

        if before:
            paragraph.append(before)
        italic_tag = soup.new_tag("i")
        italic_tag.string = matched_text
        paragraph.append(italic_tag)
        if after:
            paragraph.append(after)
        return

    italic_tag = soup.new_tag("i")
    italic_tag.string = concepto
    paragraph.append(italic_tag)
    if citation_text:
        paragraph.append(f". {citation_text}")


def generate_recurso_html(concepto, citation_text, url, template_path):
    with open(template_path, 'r', encoding='utf-8') as f:
        html = f.read()
        
    soup = BeautifulSoup(html, "html.parser")
    
    container = soup.find('div', class_='c-d403-2')
    if container:
        paragraphs = container.find_all('p')
        if len(paragraphs) >= 2:
            # First paragraph: citation with italicized concept
            _inject_italic_concept(soup, paragraphs[0], concepto, citation_text)
            
            # Second paragraph: URL
            a_tag = paragraphs[1].find('a')
            if a_tag:
                if url == "#":
                    a_tag['href'] = "#"
                    a_tag['target'] = ""
                else:
                    a_tag['href'] = url
                    
    return str(soup)

def add_glossary_entry(driver, wait, concepto, definition_html, unidad):
    """
    Adds a new entry to the currently open Glossary.
    """
    logger.info(f"--- Processing Entry: '{concepto[:50]}...' ---")
    
    # Click 'Añadir entrada'
    # Using action URL and singlebutton class to prevent matching buttons inside the edit form
    add_btn_xpath = "//div[contains(@class, 'singlebutton')]//form[contains(@action, 'glossary/edit.php')]//button | //a[contains(@href, 'glossary/edit.php') and contains(@href, 'cmid')] | //*[self::button or self::a][contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'adir entrada')]"
    try:
        add_btn = wait.until(EC.element_to_be_clickable((By.XPATH, add_btn_xpath)))
        driver.execute_script("arguments[0].click();", add_btn)
        logger.info("Clicked 'Añadir entrada' button.")
    except TimeoutException:
        logger.error("Could not find 'Añadir entrada' button.")
        return False
        
    # Wait for the form
    wait.until(EC.presence_of_element_located((By.ID, "id_concept")))
    
    # Fill Concepto
    concept_input = driver.find_element(By.ID, "id_concept")
    concept_input.clear()
    concept_input.send_keys(concepto)
    logger.info("Filled 'Concepto' field.")
    
    # Fill Definición (WYSIWYG)
    try:
        # Try different possible names for the textarea
        textarea = None
        for name in ["definition_editor[text]", "definitioneditor[text]", "definition[text]", "definition"]:
            elements = driver.find_elements(By.CSS_SELECTOR, f"textarea[name='{name}']")
            if elements:
                textarea = elements[0]
                break
                
        if not textarea:
            # Fallback to any textarea on the page
            textareas = driver.find_elements(By.TAG_NAME, "textarea")
            if textareas:
                textarea = textareas[0]
            else:
                raise Exception("No textarea found on the page!")
            
        # 1. Update the underlying textarea
        driver.execute_script("arguments[0].value = arguments[1];", textarea, definition_html)
        
        # 2. Update TinyMCE if it exists
        driver.execute_script("""
            if (typeof tinymce !== 'undefined') {
                tinymce.editors.forEach(function(editor) {
                    editor.setContent(arguments[0]);
                });
            }
        """, definition_html)
        
        # 3. Update Atto if it exists
        try:
            atto = driver.find_elements(By.CSS_SELECTOR, ".editor_atto_content")
            if atto:
                driver.execute_script("arguments[0].innerHTML = arguments[1];", atto[0], definition_html)
        except:
            pass
            
        logger.info("Injected HTML into Definición editor.")
        
    except Exception as e2:
        logger.error(f"Could not set definition HTML: {e2}")
        # IMPORTANT: Cancel to return to the glossary list so subsequent items don't fail!
        try:
            driver.find_element(By.NAME, "cancel").click()
            wait.until(EC.presence_of_element_located((By.XPATH, add_btn_xpath)))
        except:
            pass
        return False

    # Categorías
    if unidad:
        try:
            cat_select = Select(driver.find_element(By.CSS_SELECTOR, "select[name='categories[]']"))
            cat_select.deselect_all()
            for opt in cat_select.options:
                if unidad.lower() in opt.text.lower():
                    opt.click()
                    logger.info(f"Selected category: {unidad}")
                    break
        except Exception as e:
            logger.warning(f"Could not select category {unidad}: {e}")
            
    # Auto-enlace
    try:
        # Check if the fieldset is collapsed and expand it if necessary
        linking_hdr = driver.find_elements(By.CSS_SELECTOR, "a[aria-controls='id_linkinghdrcontainer']")
        if linking_hdr and linking_hdr[0].get_attribute("aria-expanded") == "false":
            driver.execute_script("arguments[0].click();", linking_hdr[0])
            time.sleep(0.5)
            
        usedynalink = driver.find_element(By.ID, "id_usedynalink")
        if not usedynalink.is_selected():
            usedynalink.click()
            logger.info("Checked 'Esta entrada será enlazada automáticamente'.")
            
        fullmatch = driver.find_element(By.ID, "id_fullmatch")
        if not fullmatch.is_selected():
            fullmatch.click()
            logger.info("Checked 'Sólo enlazar palabras completas'.")
    except Exception as e:
        logger.warning(f"Could not set auto-link options: {e}")
        
    # Save changes
    submit_btn = driver.find_element(By.ID, "id_submitbutton")
    try:
        # Native click triggers Moodle's frontend validators and sync scripts
        submit_btn.click()
    except:
        driver.execute_script("arguments[0].click();", submit_btn)
        
    logger.info("Submitted the entry. Waiting for redirect or validation feedback...")
    
    # Wait until returned to the glossary list (view mode) OR detect duplicate concept validation.
    # This avoids getting stuck on the form when Moodle blocks duplicate glossary concepts.
    try:
        wait.until(lambda d: (
            len(d.find_elements(By.CSS_SELECTOR, "body#page-mod-glossary-view")) > 0
            or len(d.find_elements(By.CSS_SELECTOR, "#id_error_concept")) > 0
        ))
    except TimeoutException:
        logger.error("Failed to redirect back to Glossary view. Form might have validation errors.")
        try:
            driver.find_element(By.NAME, "cancel").click()
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "body#page-mod-glossary-view")))
        except:
            pass
        return False
    
    concept_errors = driver.find_elements(By.CSS_SELECTOR, "#id_error_concept")
    if concept_errors:
        error_text = concept_errors[0].text.strip().lower()
        if "ya existe" in error_text and "no se permiten duplicados" in error_text:
            logger.warning(f"Concepto duplicado '{concepto}'. Clicking cancel and skipping item.")
            try:
                driver.find_element(By.NAME, "cancel").click()
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "body#page-mod-glossary-view")))
                wait.until(EC.presence_of_element_located((By.XPATH, add_btn_xpath)))
            except Exception as cancel_error:
                logger.error(f"Could not return to glossary view after duplicate warning: {cancel_error}")
            return False
    
    try:
        wait.until(EC.presence_of_element_located((By.XPATH, add_btn_xpath)))
    except TimeoutException:
        logger.error("Glossary view loaded but add-entry button was not found.")
        return False
        
    return True

def run_recursos_apoyo_workflow(driver, course_id, wait_time=10):
    """
    Iterates through weeks 1-8, extracts bibliografía & actualidad,
    and uploads them as entries to the SX - Actualidad glossary.
    """
    logger.info(f"Starting Recursos de Apoyo (Actualidad) workflow for course {course_id}...")
    wait = WebDriverWait(driver, wait_time)
    
    json_path = os.path.join("assets", str(course_id), "contenidos.json")
    if not os.path.exists(json_path):
        logger.warning(f"Mapping file {json_path} not found. Skipping workflow.")
        return False
        
    with open(json_path, "r", encoding="utf-8") as f:
        try:
            contenidos_data = json.load(f)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON in {json_path}")
            return False
            
    template_path = os.path.join("assets", "templates", "recursos_apoyo.html")
    if not os.path.exists(template_path):
        logger.error(f"Template {template_path} not found.")
        return False
            
    all_items = []
            
    for i in range(1, 9):
        week_name = f"Semana {i}"
        unidad = get_unidad_for_week(i)
        
        if week_name not in contenidos_data:
            continue
            
        # Extract bibliografía (from infografia)
        items = []
        if 'infografia' in contenidos_data[week_name] and 'slides' in contenidos_data[week_name]['infografia']:
            refs = [s for s in contenidos_data[week_name]['infografia']['slides'] if s['type'] == 'referencias']
            if refs and 'content' in refs[0]:
                logger.info(f"Extracted {len(refs[0]['content'])} reference items from Bibliografía for {week_name}.")
                items.extend(refs[0]['content'])
                
        # Extract Actualidad
        if 'actualidad' in contenidos_data[week_name]:
            actualidad_items = _normalize_actualidad_items(contenidos_data[week_name]['actualidad'])
            logger.info(f"Extracted {len(actualidad_items)} items from Actualidad for {week_name}.")
            items.extend(actualidad_items)
            
        for item in items:
            soup = BeautifulSoup(item, "html.parser")
            clean_item_text = soup.get_text(separator=' ', strip=True)
            
            # Extract URL if hidden in an anchor tag and missing from raw text
            a_tags = soup.find_all("a", href=True)
            if a_tags:
                href = a_tags[0]["href"].strip()
                if href.startswith("http") and href not in clean_item_text:
                    clean_item_text += f" {href}"
                    
            # Skip empty items or placeholders explicitly named 'Concepto'
            if clean_item_text and clean_item_text.lower() not in ["concepto", "concepto.", "concepto "]:
                all_items.append({"text": clean_item_text, "unidad": unidad, "week": week_name})
                
    # Deduplicate while preserving order
    clean_items = []
    seen = set()
    for item in all_items:
        if item["text"] not in seen:
            seen.add(item["text"])
            clean_items.append(item)
            
    if not clean_items:
        logger.info("No recursos items found to upload.")
        return True
        
    logger.info(f"Found {len(clean_items)} unique items. Navigating to 'Recursos de apoyo' Glossary...")
    
    # Navigate to course page
    if "course/view.php" not in driver.current_url or "&section=" in driver.current_url:
        navigate_to_course(driver, Config.MOODLE_URL, course_id, wait_time)
        
    # Find and enter the central "Recursos de apoyo" Glossary activity
    try:
        activity_xpath = "//li[contains(@class, 'activity')]//*[contains(@class, 'instancename') and contains(text(), 'Recursos de apoyo')]"
        activity_title = wait.until(EC.presence_of_element_located((By.XPATH, activity_xpath)))
        a_element = activity_title.find_element(By.XPATH, "./ancestor::a")
        driver.execute_script("arguments[0].click();", a_element)
        
        # Wait for Glossary page to load
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "body#page-mod-glossary-view")))
    except Exception as e:
        logger.error(f"Could not find or enter 'Recursos de apoyo' Glossary: {e}")
        return False
        
    # Process each item
    success_count = 0
    fail_count = 0
    missing_url_items = []
    
    for item in clean_items:
        concepto, citation_text, url = extract_reference_data(item["text"])
        
        if url == "#":
            missing_url_items.append(f"[{item.get('week', 'N/A')}] {concepto}")
        logger.info(f"Extracted Concepto: '{concepto}'")
        logger.info(f"Extracted URL: '{url}'")
        
        final_html = generate_recurso_html(concepto, citation_text, url, template_path)
        success = add_glossary_entry(driver, wait, concepto, final_html, item["unidad"])
        
        if success:
            success_count += 1
            logger.info(f"Successfully finished adding '{concepto}'.\n")
        else:
            fail_count += 1
            logger.error(f"Failed to add '{concepto}'.\n")
            
        time.sleep(1)
            
    if missing_url_items:
        log_dir = os.path.join("assets", str(course_id), "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "missing_urls.log")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\n--- Recursos de Apoyo (Course {course_id}) ---\n")
            for m in missing_url_items:
                f.write(f"{m}\n")
        logger.info(f"Logged {len(missing_url_items)} items with missing URLs to {log_file}")

    logger.info("=====================================================")
    logger.info(f"Recursos de Apoyo workflow complete.")
    logger.info(f"Total entries processed: {len(clean_items)}")
    logger.info(f"Successful uploads: {success_count}")
    logger.info(f"Failed uploads: {fail_count}")
    logger.info("=====================================================")
    
    return True
