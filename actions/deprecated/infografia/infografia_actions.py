import logging
import os
import json
import sys
import time
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# Add project root to sys.path to ensure local modules are accessible
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from actions.infografia.infografia_extractor import parse_infografia_html
from actions.infografia.infografia_builder import generate_infografia_html
from actions.moodle_actions import navigate_to_course, upload_moodle_wysiwyg
from config.settings import Config
from html_generator.generate_html import clean_html

logger = logging.getLogger(__name__)

def process_infografia_html(raw_html):
    """
    Cleans the raw HTML and extracts/removes all elements with depositphotos.com URLs.
    Strips inline styles, classes, and meaningless span tags to leave a clean structure.
    Returns a dictionary with 'html_content' and 'deposit_photos' (list of URLs).
    """
    deposit_photos_urls = []
    
    if not raw_html:
        return {"html_content": "", "deposit_photos": []}
        
    soup = BeautifulSoup(raw_html, "html.parser")
    
    # Find all elements (like <img> or <a>) that have a depositphotos.com URL in src or href
    for tag in soup.find_all(True):
        url = None
        if tag.has_attr('src') and 'depositphotos.com' in tag['src']:
            url = tag['src']
        elif tag.has_attr('href') and 'depositphotos.com' in tag['href']:
            url = tag['href']
            
        if url:
            deposit_photos_urls.append(url)
            tag.extract()
            
    # Clean up inline styles, classes, and spans
    for tag in soup.find_all(True):
        # Unwrap span and font tags as they usually just hold styles
        if tag.name in ['span', 'font', 'div']:
            tag.unwrap()
        else:
            # Keep only essential attributes
            attrs = dict(tag.attrs)
            tag.attrs = {}
            if tag.name == 'a' and 'href' in attrs:
                tag['href'] = attrs['href']
            if tag.name == 'img' and 'src' in attrs:
                tag['src'] = attrs['src']
                if 'alt' in attrs:
                    tag['alt'] = attrs['alt']
            
    cleaned_soup_str = str(soup)
    final_html = clean_html(cleaned_soup_str)
    
    return {
        "html_content": final_html,
        "deposit_photos": deposit_photos_urls
    }

def extract_infografia_content(driver, week_name, wait_time=10):
    """
    Navigates to the 'VIR - INFOGRAFÍA INTERACTIVA' resource in the specified week,
    enters its settings (Editar ajustes), and extracts the WYSIWYG 'Contenido de la página' HTML.
    Returns the raw HTML string, or None if failed.
    """
    wait = WebDriverWait(driver, wait_time)
    resource_name = "VIR - INFOGRAFÍA INTERACTIVA"
    logger.info(f"Extracting {resource_name} from '{week_name}'")
    
    try:
        # 1. Locate the section wrapper containing the text for the week
        # Use a quick wait first
        try:
            quick_wait = WebDriverWait(driver, 3)
            quick_xpath = f"//li[contains(@class, 'section')]//*[contains(., '{week_name}')]"
            quick_wait.until(EC.presence_of_element_located((By.XPATH, quick_xpath)))
        except TimeoutException:
            logger.warning(f"Section '{week_name}' not found on the page.")
            return None

        title_xpath = (
            f"//li[contains(@class, 'section')]//*[contains(@class, 'sectionname') or self::h3 or self::h4]"
            f"[contains(., '{week_name}')]"
        )
        title_element = wait.until(EC.presence_of_element_located((By.XPATH, title_xpath)))
        section_li = title_element.find_element(By.XPATH, "./ancestor::li[contains(@class, 'section')]")
        
        # 2. Scope down to the specific activity "VIR - INFOGRAFÍA INTERACTIVA" within this section
        # Look for the instance name
        activity_xpath = f".//li[contains(@class, 'activity')]//*[contains(@class, 'instancename') and contains(text(), '{resource_name}')]"
        try:
            activity_title = section_li.find_element(By.XPATH, activity_xpath)
        except Exception:
            logger.warning(f"Resource '{resource_name}' not found in '{week_name}'.")
            return None
            
        activity_li = activity_title.find_element(By.XPATH, "./ancestor::li[contains(@class, 'activity')]")
        
        # 3. Open the "Editar" dropdown for this activity
        dropdown_toggle = activity_li.find_element(By.CSS_SELECTOR, "a.dropdown-toggle[title='Editar'], a[aria-label='Editar']")
        try:
            wait.until(EC.element_to_be_clickable(dropdown_toggle)).click()
        except WebDriverException:
            driver.execute_script("arguments[0].click();", dropdown_toggle)
            
        # 4. Click "Editar ajustes"
        edit_option_xpath = ".//a[contains(@class, 'dropdown-item') and (contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'editar ajustes') or contains(@href, 'modedit.php'))]"
        edit_option = wait.until(lambda d: activity_li.find_element(By.XPATH, edit_option_xpath))
        edit_href = edit_option.get_attribute("href")
        
        original_window = driver.current_window_handle
        use_new_tab = Config.ENABLE_INFOGRAFIA_EXPORT and edit_href
        
        if use_new_tab:
            driver.execute_script("window.open(arguments[0], '_blank');", edit_href)
            for window_handle in driver.window_handles:
                if window_handle != original_window:
                    driver.switch_to.window(window_handle)
                    break
        else:
            try:
                wait.until(EC.element_to_be_clickable(edit_option)).click()
            except WebDriverException:
                driver.execute_script("arguments[0].click();", edit_option)
            
        # 5. Wait for the edit page to load (look for page content textarea or #id_page)
        logger.info("Waiting for resource settings page to load...")
        # Give it a moment to render the form
        time.sleep(1)
        
        # In Moodle mod_page, the content field is usually named 'page[text]'
        # Try to find the textarea that holds the HTML content
        textarea_css = "textarea[name='page[text]']"
        try:
            textarea = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, textarea_css)))
            
            # The textarea might be synced automatically or we can extract its value
            # Usually, when the page loads, the textarea contains the exact raw HTML from the DB.
            raw_html = driver.execute_script("return arguments[0].value;", textarea)
            
            # If empty, try getting it from Atto editor directly as a fallback
            if not raw_html or not raw_html.strip():
                logger.info("Textarea was empty, checking Atto editor innerHTML...")
                try:
                    atto_editor = driver.find_element(By.CSS_SELECTOR, "#fitem_id_page .editor_atto_content")
                    raw_html = driver.execute_script("return arguments[0].innerHTML;", atto_editor)
                except Exception:
                    pass
                    
        except TimeoutException:
            logger.error(f"Could not find the 'Contenido de la página' editor for '{week_name}'.")
            if use_new_tab:
                driver.close()
                driver.switch_to.window(original_window)
            else:
                driver.back()
            return None
            
        # 6. Navigate back to the course page
        if use_new_tab:
            driver.close()
            driver.switch_to.window(original_window)
        else:
            driver.back()
            # Wait until we are back on the course view
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "body.path-course-view")))
        
        return raw_html
        
    except Exception as e:
        logger.error(f"Failed to extract infografia from '{week_name}': {e}")
        # Try to return to a safe state if an exception occurs mid-navigation
        try:
            if "original_window" in locals() and "use_new_tab" in locals() and use_new_tab:
                if driver.current_window_handle != original_window:
                    driver.close()
                    driver.switch_to.window(original_window)
            elif "modedit.php" in driver.current_url:
                driver.back()
        except Exception:
            pass
        return None



def run_infografia_export_workflow(driver, course_id, base_url, wait_time=10):
    """
    Iterates through weeks 1-8, extracts the infographic content, processes it,
    saves it to the contenidos.json file, generates final HTML using templates,
    and uploads it to Moodle.
    """
    logger.info(f"Starting Infografia export workflow for course {course_id}...")
    
    json_path = os.path.join("assets", str(course_id), "contenidos.json")
    if not os.path.exists(json_path):
        logger.warning(f"Mapping file {json_path} not found. Skipping infografia export.")
        return False
        
    with open(json_path, "r", encoding="utf-8") as f:
        try:
            contenidos_data = json.load(f)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON in {json_path}")
            return False
            
    # Iterate from Semana 1 to Semana 8
    updated = False
    for i in range(1, 9):
        week_name = f"Semana {i}"
        
        # Only process if this week exists in the json
        if week_name not in contenidos_data:
            logger.info(f"{week_name} not found in json data, skipping.")
            continue
            
        # Ensure we are on the main course page before extracting
        # Only navigate if we are stuck on a specific section page or outside the course view
        if "course/view.php" not in driver.current_url or "&section=" in driver.current_url:
            navigate_to_course(driver, Config.MOODLE_URL, course_id, wait_time)
        
        raw_html = extract_infografia_content(driver, week_name, wait_time)
        if raw_html is not None:
            # Save the raw HTML before any processing
            raw_output_path = os.path.join("assets", str(course_id), "infografias", "raw", f"RAW_s{i}_infografia.html")
            os.makedirs(os.path.dirname(raw_output_path), exist_ok=True)
            with open(raw_output_path, "w", encoding="utf-8") as f:
                f.write(raw_html)
            logger.info(f"Saved raw infografia HTML for {week_name} at {raw_output_path}")

            parsed_data = parse_infografia_html(raw_html)
            
            # Update the json data structure
            contenidos_data[week_name]["infografia"] = parsed_data
            updated = True
            logger.info(f"Successfully parsed infografia for {week_name}")
            
            # Generate the final HTML
            course_title = contenidos_data.get("nombre del curso", "Nombre del curso")
            presentation_title = contenidos_data[week_name].get("nombre", f"Presentación {week_name}")
            infografia_subtitle = parsed_data.get("infografia_subtitle", "")

            final_html = generate_infografia_html(parsed_data, base_url, i, course_title, presentation_title, infografia_subtitle)

            
            # Save the final HTML locally
            output_path = os.path.join("assets", str(course_id), "infografias", f"s{i}_infografia.html")
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(final_html)
                
            logger.info(f"Generated infografia HTML for {week_name} at {output_path}")
            
            # Upload to Moodle
            resource_name = f"S{i} | Infografía"
            success = upload_moodle_wysiwyg(driver, course_id, week_name, resource_name, final_html, wait_time)
            if success:
                logger.info(f"Successfully uploaded Infografía HTML to {week_name}")
            else:
                logger.error(f"Failed to upload Infografía HTML to {week_name}")
            
            # Brief pause before next extraction
            time.sleep(1)
            
    if updated:
        # Save the updated JSON back to file
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(contenidos_data, f, ensure_ascii=False, indent=4)
        logger.info(f"Successfully updated {json_path} with infografia content.")
    else:
        logger.info("No infografia content was extracted or updated.")
        
    return True
