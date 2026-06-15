import logging
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

from actions.moodle_actions import navigate_to_course
from config.settings import Config

logger = logging.getLogger(__name__)

def run_recursos_apoyo_edit_classes_workflow(driver, course_id, wait_time=10):
    """
    Navigates to 'Recursos de apoyo', clicks 'TODAS', and edits each entry to 
    replace 'txt-blue' with 'txt-v-blue' in the definition.
    """
    logger.info(f"Starting Recursos de Apoyo (Edit Classes) workflow for course {course_id}...")
    wait = WebDriverWait(driver, wait_time)
    
    # Build URL mapping from contenidos.json
    import json
    import os
    import re
    from bs4 import BeautifulSoup
    from actions.recursos_apoyo_actions import _normalize_actualidad_items, extract_reference_data
    
    json_path = os.path.join("assets", str(course_id), "contenidos.json")
    concepto_to_url = {}
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                contenidos_data = json.load(f)
                
            for i in range(1, 9):
                week_name = f"Semana {i}"
                if week_name not in contenidos_data:
                    continue
                
                items = []
                if 'infografia' in contenidos_data[week_name] and 'slides' in contenidos_data[week_name]['infografia']:
                    refs = [s for s in contenidos_data[week_name]['infografia']['slides'] if s['type'] == 'referencias']
                    if refs and 'content' in refs[0]:
                        items.extend(refs[0]['content'])
                        
                if 'actualidad' in contenidos_data[week_name]:
                    actualidad_items = _normalize_actualidad_items(contenidos_data[week_name]['actualidad'])
                    items.extend(actualidad_items)
                    
                for item in items:
                    soup = BeautifulSoup(item, "html.parser")
                    clean_item_text = soup.get_text(separator=' ', strip=True)
                    a_tags = soup.find_all("a", href=True)
                    if a_tags:
                        href = a_tags[0]["href"].strip()
                        if href.startswith("http") and href not in clean_item_text:
                            clean_item_text += f" {href}"
                            
                    if clean_item_text and clean_item_text.lower() not in ["concepto", "concepto.", "concepto "]:
                        concepto, _, url = extract_reference_data(clean_item_text)
                        if url != "#":
                            key = concepto.strip().rstrip(':').lower()
                            concepto_to_url[key] = url
        except Exception as e:
            logger.error(f"Failed to build URL mapping from {json_path}: {e}")

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
        logger.info("Entered 'Recursos de apoyo' Glossary.")
    except Exception as e:
        logger.error(f"Could not find or enter 'Recursos de apoyo' Glossary: {e}")
        return False
        
    # Click on "TODAS"
    try:
        # Find the TODAS link using the exact text or href containing page=-1
        todas_xpath = "//a[text()='TODAS' or contains(@href, 'page=-1')]"
        todas_tab = wait.until(EC.presence_of_element_located((By.XPATH, todas_xpath)))
        driver.execute_script("arguments[0].click();", todas_tab)
        
        # Wait for page to refresh and load items
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "body#page-mod-glossary-view")))
        time.sleep(2) # Additional sleep for stability after JS/page reload
        logger.info("Clicked on 'TODAS' tab.")
    except TimeoutException:
        logger.warning("Could not find 'TODAS' tab, perhaps already viewing all or no entries exist.")
    
    # Collect all edit links
    edit_links = []
    try:
        # Edit buttons in glossary usually link to edit.php?cmid=...&id=...
        # They have title="Editar"
        edit_elements = driver.find_elements(By.XPATH, "//a[contains(@href, 'edit.php') and @title='Editar']")
        
        # If the above doesn't work, fallback to links with an edit icon
        if not edit_elements:
             edit_elements = driver.find_elements(By.XPATH, "//a[contains(@href, 'edit.php') and .//i[contains(@class, 'fa-pen') or contains(@class, 'fa-cog')]]")

        for el in edit_elements:
            href = el.get_attribute("href")
            if href and "id=" in href and "cmid=" in href:
                if href not in edit_links:
                    edit_links.append(href)
                        
        logger.info(f"Found {len(edit_links)} items to edit.")
    except Exception as e:
        logger.error(f"Could not extract edit links: {e}")
        return False

    success_count = 0
    fail_count = 0

    # Iterate and edit each entry
    main_window = driver.current_window_handle
    for index, edit_url in enumerate(edit_links):
        logger.info(f"Editing item {index + 1} of {len(edit_links)} in new tab...")
        try:
            # Open in a new tab
            driver.execute_script(f"window.open('{edit_url}', '_blank');")
            time.sleep(1) # Wait for tab to open
            
            # Switch to the new tab
            driver.switch_to.window(driver.window_handles[-1])
            
            # Wait for the edit form to load
            wait.until(EC.presence_of_element_located((By.ID, "id_concept")))
            
            # Find the editor content
            # Try to fetch current content from TinyMCE/Atto or textarea directly
            current_html = ""
            
            # Get underlying textarea value
            textarea = None
            for name in ["definition_editor[text]", "definitioneditor[text]", "definition[text]", "definition"]:
                elements = driver.find_elements(By.CSS_SELECTOR, f"textarea[name='{name}']")
                if elements:
                    textarea = elements[0]
                    break
            
            if textarea:
                current_html = textarea.get_attribute("value")
                
            # If TinyMCE/Atto is loaded, its value might be different or we might want to get it directly
            editor_html = driver.execute_script("""
                if (typeof tinymce !== 'undefined' && tinymce.editors.length > 0) {
                    return tinymce.editors[0].getContent();
                } else {
                    var atto = document.querySelector('.editor_atto_content');
                    if (atto) return atto.innerHTML;
                }
                return null;
            """)
            
            if editor_html is not None:
                current_html = editor_html
                
            if not current_html:
                current_html = ""
                
            # Perform replacements
            needs_update = False
            new_html = current_html
            
            if "txt-blue" in new_html and "txt-v-blue" not in new_html:
                new_html = new_html.replace("txt-blue", "txt-v-blue")
                needs_update = True
                logger.info("Replaced 'txt-blue' with 'txt-v-blue'.")
                
            if "R1:" in new_html:
                new_html = new_html.replace("R1:", "")
                needs_update = True
                logger.info("Removed 'R1:'.")
                
            if "R2:" in new_html:
                new_html = new_html.replace("R2:", "")
                needs_update = True
                logger.info("Removed 'R2:'.")
                
            # Check if the concepto has a trailing colon and needs updating
            current_concepto = ""
            concept_input = None
            try:
                concept_input = driver.find_element(By.ID, "id_concept")
                current_concepto = concept_input.get_attribute("value").strip()
            except Exception:
                pass

            if current_concepto and current_concepto.endswith(":"):
                new_concepto = current_concepto[:-1].strip()
                concept_input.clear()
                concept_input.send_keys(new_concepto)
                needs_update = True
                logger.info(f"Removed colon from concepto. New concepto: '{new_concepto}'")
                current_concepto = new_concepto

            # Check for missing URLs
            lookup_key = current_concepto.rstrip(':').lower().strip() if current_concepto else ""
            if 'href="#"' in new_html and lookup_key in concepto_to_url:
                real_url = concepto_to_url[lookup_key]
                new_html = re.sub(r'href="#"(?:\s*target="")?', f'href="{real_url}" target="_blank"', new_html)
                needs_update = True
                logger.info(f"Injected missing URL: {real_url}")
                
            # Ensure all links have target="_blank"
            if "<a " in new_html.lower():
                soup_html = BeautifulSoup(new_html, "html.parser")
                a_modified = False
                for a_tag in soup_html.find_all("a", href=True):
                    if a_tag.get("target") != "_blank":
                        a_tag["target"] = "_blank"
                        a_modified = True
                if a_modified:
                    new_html = str(soup_html)
                    needs_update = True
                    logger.info("Added target=\"_blank\" to links.")

            if needs_update:
                # Update editor
                if textarea:
                    driver.execute_script("arguments[0].value = arguments[1];", textarea, new_html)
                    
                driver.execute_script("""
                    if (typeof tinymce !== 'undefined') {
                        tinymce.editors.forEach(function(editor) {
                            editor.setContent(arguments[0]);
                        });
                    }
                    var atto = document.querySelector('.editor_atto_content');
                    if (atto) {
                        atto.innerHTML = arguments[0];
                    }
                """, new_html)
                
                # Save changes
                submit_btn = driver.find_element(By.ID, "id_submitbutton")
                driver.execute_script("arguments[0].scrollIntoView(true);", submit_btn)
                time.sleep(0.5)
                try:
                    submit_btn.click()
                except:
                    driver.execute_script("arguments[0].click();", submit_btn)
                    
                # Wait for redirect back to glossary list to confirm save
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "body#page-mod-glossary-view")))
                success_count += 1
            else:
                logger.info("No 'txt-blue', 'R1:', or 'R2:' found to modify. Skipping.")
                success_count += 1 # consider it a success if nothing needed changing
                
        except Exception as e:
            logger.error(f"Failed to edit item {index + 1}: {e}")
            fail_count += 1
        finally:
            # Always ensure we close the new tab and switch back to the main window
            try:
                if len(driver.window_handles) > 1:
                    driver.close()
                driver.switch_to.window(main_window)
            except Exception as close_error:
                logger.error(f"Error handling tabs: {close_error}")
                # Fallback to switch back to main
                try:
                    driver.switch_to.window(driver.window_handles[0])
                except:
                    pass
                
    logger.info("=====================================================")
    logger.info(f"Recursos de Apoyo (Edit Classes) workflow complete.")
    logger.info(f"Total items found: {len(edit_links)}")
    logger.info(f"Successful processing: {success_count}")
    logger.info(f"Failed processing: {fail_count}")
    logger.info("=====================================================")
    
    return True
