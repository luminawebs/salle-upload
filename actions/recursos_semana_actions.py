import logging
import os
import json
import csv
import re
import time
from bs4 import BeautifulSoup

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from actions.moodle_actions import navigate_to_course
from config.settings import Config
from core.wysiwyg_handler import inject_html_into_wysiwyg

logger = logging.getLogger(__name__)

def _decode_html_entities(text: str) -> str:
    """Replace common HTML entities with their UTF-8 equivalents."""
    entities = {
        "&aacute;": "á", "&eacute;": "é", "&iacute;": "í",
        "&oacute;": "ó", "&uacute;": "ú", "&ntilde;": "ñ",
        "&Aacute;": "Á", "&Eacute;": "É", "&Iacute;": "Í",
        "&Oacute;": "Ó", "&Uacute;": "Ú", "&Ntilde;": "Ñ",
        "&uuml;": "ü", "&Uuml;": "Ü",
        "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"',
        "&nbsp;": " ", "&ordm;": "º", "&ordf;": "ª",
        "&ndash;": "–", "&mdash;": "—",
        "&ldquo;": "\u201c", "&rdquo;": "\u201d",
        "&lsquo;": "\u2018", "&rsquo;": "\u2019",
        "&#279;": "ę",
    }
    for entity, char in entities.items():
        text = text.replace(entity, char)
    return text

def _make_book_name_bold(text: str) -> str:
    """
    Finds a citation pattern: Author. (Date). Title. Publisher.
    and makes the Title (book name) bold.
    """
    # Match the date part like (YYYY) or (YYYY, 15 de abril)
    match = re.search(r'(^.*?\(\d{4}[^\)]*\)\.\s+)', text)
    if not match:
        return text
        
    start_part = match.group(1)
    rest = text[len(start_part):]
    
    paren_depth = 0
    title_end = -1
    for i, char in enumerate(rest):
        if char == '(':
            paren_depth += 1
        elif char == ')':
            paren_depth = max(0, paren_depth - 1)
        elif char == '.' and paren_depth == 0:
            # Avoid breaking at common abbreviations
            if i >= 2 and rest[i-2:i].lower() == 'pp':
                continue
            if i >= 2 and rest[i-2:i].lower() == 'ed':
                continue
            title_end = i
            break
            
    if title_end != -1:
        title = rest[:title_end]
        after_title = rest[title_end:]
        return f"{start_part}<strong>{title}</strong>{after_title}"
    else:
        return f"{start_part}<strong>{rest}</strong>"

def _clean_csv_text_to_html(text: str) -> str:
    """
    Cleans the resources plaintext from CSV by:
    - Splitting by newlines into paragraphs
    - Removing URLs (http/https and www.)
    - Removing 'Recurso X:' or 'RX:'
    - Removing '●'
    - Bolding the book name
    """
    if not text:
        return ""
        
    lines = text.split('\n')
    html_fragments = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Remove URLs
        line = re.sub(r'(?i)(?:recuperado\s+de|consultado\s+en|disponible\s+en)?\s*https?://[^\s<>"]+|www\.[^\s<>"]+', '', line)
        
        # Remove "Recurso 1:", "Recurso 2:", "R1:", "R2:"
        line = re.sub(r'(?i)\b(?:Recurso\s*\d+|R\d+):\s*', '', line)
        
        # Remove bullet point character
        line = line.replace('●', '')
        
        # Clean up empty parens left behind by URL removal (e.g., "( )")
        line = line.replace('()', '').replace('( )', '').replace(' .', '.')
        
        # Clean up empty italics tags if the URL was inside them
        line = line.replace('<i></i>', '').replace('<em></em>', '')
        
        line = line.strip()
        if line:
            line = _make_book_name_bold(line)
            html_fragments.append(f"<p>{line}</p>")
            
    return "\n".join(html_fragments)

def generate_recursos_semana_html(basicos_html: str, comp_html: str, template_path: str, output_path: str) -> bool:
    """
    Fills the recursos.html template with the extracted data.
    """
    if not os.path.exists(template_path):
        logger.error(f"Template {template_path} not found.")
        return False
        
    with open(template_path, "r", encoding="utf-8") as f:
        template_html = f.read()
        
    soup = BeautifulSoup(template_html, "html.parser")
    
    # Locate the "Recursos y medios educativos básicos" h4
    basicos_h4 = soup.find(lambda t: t.name == "h4" and "básicos" in t.get_text(strip=True).lower())
    if basicos_h4:
        container = basicos_h4.parent
        virtual_recurso = container.parent
        
        if basicos_html:
            # Remove existing <p> sibling elements
            for sibling in list(basicos_h4.find_next_siblings("p")):
                sibling.extract()
            # Append new html
            new_content = BeautifulSoup(basicos_html, "html.parser")
            for node in list(new_content.contents):
                container.append(node)
        else:
            # If no basicos_html, remove the whole section
            if virtual_recurso and "virtual-recurso-1" in virtual_recurso.get("class", []):
                virtual_recurso.extract()
            else:
                container.extract()

    # Locate the "Recursos digitales complementarios" h4
    comp_h4 = soup.find(lambda t: t.name == "h4" and "complementarios" in t.get_text(strip=True).lower())
    if comp_h4:
        container = comp_h4.parent
        virtual_recurso = container.parent
        
        if comp_html:
            # Remove existing <p> sibling elements
            for sibling in list(comp_h4.find_next_siblings("p")):
                sibling.extract()
            # Append new html
            new_content = BeautifulSoup(comp_html, "html.parser")
            for node in list(new_content.contents):
                container.append(node)
        else:
            # If no comp_html, remove the whole section
            if virtual_recurso and "virtual-recurso-1" in virtual_recurso.get("class", []):
                virtual_recurso.extract()
            else:
                container.extract()
            
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(soup.prettify())
        
    return True

def _upload_html_to_moodle(driver, course_id: int, week_name: str, html_content: str, wait_time: int) -> bool:
    """
    Navigates to the "SX | Recursos" item in the given week and uploads the HTML.
    """
    resource_name = f"S{week_name.split(' ')[-1]} | Recursos"
    logger.info(f"Uploading to {resource_name}...")
    
    if "course/view.php" not in driver.current_url:
        navigate_to_course(driver, Config.MOODLE_URL, course_id, wait_time)
        
    wait = WebDriverWait(driver, wait_time)
    
    try:
        # Find the activity
        activity_xpath = f"//li[contains(@class, 'activity')]//*[contains(@class, 'instancename') and contains(text(), '{resource_name}')]"
        try:
            activity_title = wait.until(EC.presence_of_element_located((By.XPATH, activity_xpath)))
        except TimeoutException:
            logger.warning(f"  Resource '{resource_name}' not found.")
            return False
            
        activity_li = activity_title.find_element(By.XPATH, "./ancestor::li[contains(@class, 'activity')]")
        
        # Click edit dropdown
        dropdown_toggle = activity_li.find_element(By.CSS_SELECTOR, "a.dropdown-toggle[title='Editar'], a[aria-label='Editar']")
        try:
            wait.until(EC.element_to_be_clickable(dropdown_toggle)).click()
        except:
            driver.execute_script("arguments[0].click();", dropdown_toggle)
            
        # Click edit settings
        edit_option_xpath = ".//a[contains(@class, 'dropdown-item') and (contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'editar ajustes') or contains(@href, 'modedit.php'))]"
        edit_option = wait.until(lambda d: activity_li.find_element(By.XPATH, edit_option_xpath))
        
        main_window = driver.current_window_handle
        href = edit_option.get_attribute("href")
        
        if href:
            driver.execute_script(f"window.open('{href}', '_blank');")
            driver.switch_to.window(driver.window_handles[-1])
        else:
            try:
                wait.until(EC.element_to_be_clickable(edit_option)).click()
            except:
                driver.execute_script("arguments[0].click();", edit_option)
            
        # Wait for page to load
        submit_btn_css = "#id_submitbutton, input[name='submitbutton'], button[name='submitbutton']"
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, submit_btn_css)))
        
        # Inject HTML into the 'contenido' section (page[text])
        success = inject_html_into_wysiwyg(driver, html_content, wait_time, target_section="contenido")
        if not success:
            logger.warning(f"  Injection into {resource_name} reported failure.")
            
        # Close the new tab and switch back
        if len(driver.window_handles) > 1:
            driver.close()
            driver.switch_to.window(main_window)
            
        return True
    except Exception as e:
        logger.error(f"  Error uploading {resource_name}: {e}")
        try:
            cancel_btn = driver.find_element(By.CSS_SELECTOR, "input[name='cancel']")
            driver.execute_script("arguments[0].click();", cancel_btn)
            time.sleep(1)
        except:
            pass
            
        # Close the new tab and switch back if an error occurred
        if 'main_window' in locals() and len(driver.window_handles) > 1:
            try:
                driver.close()
                driver.switch_to.window(main_window)
            except:
                pass
                
        return False

def run_recursos_html_export_workflow(driver, course_id: int, wait_time=10):
    """
    Main workflow to extract recursos from Propuesta_Metodológica.csv (or fallback to recursos.csv),
    clean them, populate the template, and upload to Moodle.
    """
    logger.info(f"Starting Recursos HTML Export Workflow for course {course_id}...")
    
    recursos_data = {}
    
    # 1. Try reading from Propuesta_Metodológica.csv first
    csv_path_propuesta = os.path.join("assets", str(course_id), "Propuesta_Metodológica.csv")
    csv_path_fallback = os.path.join("assets", str(course_id), "recursos", "recursos.csv")
    
    loaded_from_propuesta = False
    if os.path.exists(csv_path_propuesta):
        try:
            try:
                f = open(csv_path_propuesta, 'r', encoding='utf-8-sig')
                headers = next(csv.reader(f))
            except UnicodeDecodeError:
                f = open(csv_path_propuesta, 'r', encoding='cp1252')
                headers = next(csv.reader(f))
                
            f.seek(0)
            reader = csv.reader(f)
            headers = next(reader)
            
            semana_idx = next((i for i, h in enumerate(headers) if 'SEMANA DE ESTUDIO' in h.upper()), None)
            basicos_idx = next((i for i, h in enumerate(headers) if 'RECURSOS EDUCATIVOS BÁSICOS' in h.upper()), None)
            comp_idx = next((i for i, h in enumerate(headers) if 'RECURSOS COMPLEMENTARIOS' in h.upper()), None)
            
            if semana_idx is not None and basicos_idx is not None and comp_idx is not None:
                for row in reader:
                    if len(row) > max(semana_idx, basicos_idx, comp_idx):
                        week_num = row[semana_idx].strip()
                        if week_num and week_num.isdigit():
                            recursos_data[week_num] = {
                                "basicos": row[basicos_idx].strip(),
                                "complementarios": row[comp_idx].strip()
                            }
                loaded_from_propuesta = True
                logger.info(f"Loaded recursos from {csv_path_propuesta}")
            f.close()
        except Exception as e:
            logger.error(f"Failed to read from Propuesta_Metodológica.csv: {e}")

    # 2. Fallback to recursos.csv if we couldn't load from Propuesta_Metodológica.csv
    if not loaded_from_propuesta:
        if not os.path.exists(csv_path_fallback):
            logger.warning(f"Neither {csv_path_propuesta} nor {csv_path_fallback} found (or valid). Skipping workflow.")
            return False
            
        with open(csv_path_fallback, newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            try:
                next(reader) # skip header
            except StopIteration:
                pass
            for row in reader:
                if len(row) >= 3:
                    week_num = row[0].strip()
                    if week_num:
                        recursos_data[week_num] = {
                            "basicos": row[1].strip(),
                            "complementarios": row[2].strip()
                        }
        logger.info(f"Loaded recursos from {csv_path_fallback}")
            
    template_path = os.path.join("assets", "templates", "recursos.html")
    
    success_count = 0
    fail_count = 0
    
    for i in range(1, 9):
        week_name = f"Semana {i}"
        week_str = str(i)
        
        basicos_html = ""
        comp_html = ""
        
        if week_str in recursos_data:
            basicos_text = recursos_data[week_str]["basicos"]
            comp_text = recursos_data[week_str]["complementarios"]
            
            basicos_html = _clean_csv_text_to_html(basicos_text)
            comp_html = _clean_csv_text_to_html(comp_text)
        
        # Output path for debugging
        output_path = os.path.join("assets", str(course_id), "recursos", f"S{i}_recursos.html")
        
        # Generate the file
        if generate_recursos_semana_html(basicos_html, comp_html, template_path, output_path):
            with open(output_path, "r", encoding="utf-8") as f:
                final_html = f.read()
                
            if _upload_html_to_moodle(driver, course_id, week_name, final_html, wait_time):
                success_count += 1
            else:
                fail_count += 1
        else:
            fail_count += 1
            
    logger.info("=====================================================")
    logger.info(f"Recursos HTML Export workflow complete.")
    logger.info(f"Successful uploads: {success_count}")
    logger.info(f"Failed uploads: {fail_count}")
    logger.info("=====================================================")
    
    return True
