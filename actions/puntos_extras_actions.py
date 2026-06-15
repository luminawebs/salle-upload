"""
puntos_extras_actions.py
------------------------
Automates the process of converting local DOCX files to Moodle GIFT format
and uploading them to the "SX | Puntos extras" quizzes.
"""

import logging
import os
import re
import time
from docx import Document

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

from actions.moodle_actions import navigate_to_course
from config.settings import Config

logger = logging.getLogger(__name__)

PUNTOS_WEEKS = ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"]

def convert_docx_to_gift(docx_path: str, output_txt_path: str) -> bool:
    """
    Reads a DOCX file containing multiple-choice questions, parses it,
    and writes a Moodle GIFT formatted .txt file.
    """
    logger.info(f"Converting DOCX to GIFT: {docx_path}")
    try:
        doc = Document(docx_path)
    except Exception as e:
        logger.error(f"Failed to read DOCX file {docx_path}: {e}")
        return False

    text = '\n'.join([p.text for p in doc.paragraphs if p.text.strip()])

    # Split by 'Pregunta N'
    questions = re.split(r'(?i)^(Pregunta\s+(\d+))\s*$', text, flags=re.MULTILINE)
    
    if len(questions) < 3:
        logger.warning(f"No questions found in {docx_path} matching 'Pregunta N'")
        return False

    gift_lines = []
    
    # questions list structure: ['', 'Pregunta 1', '1', 'Body...', 'Pregunta 2', '2', 'Body...']
    for i in range(1, len(questions), 3):
        if i + 2 >= len(questions):
            break
            
        q_label = questions[i].strip() # e.g., 'Pregunta 1'
        q_num = questions[i+1].strip() # e.g., '1'
        q_body = questions[i+2].strip()
        
        # Match the start of the first option, which usually looks like =A., ~B., A., etc.
        match = re.search(r'^(=?[A-Da-d]\.\s*)', q_body, flags=re.MULTILINE)
        if not match:
            logger.warning(f"Could not find options for {q_label} in {docx_path}")
            continue
            
        stem = q_body[:match.start()].strip()
        options_text = q_body[match.start():].strip()
        
        # Format options
        options = []
        for opt_line in options_text.split('\n'):
            opt_line = opt_line.strip()
            if not opt_line: 
                continue
            
            # Match '=A. text', '~B. text', 'C. text', '= D. text', etc.
            opt_match = re.match(r'^(=?)\s*[A-Da-d]\.\s*(.*)$', opt_line)
            if opt_match:
                is_correct = opt_match.group(1) == '='
                opt_text = opt_match.group(2)
                prefix = '=' if is_correct else '~'
                options.append(f'\t{prefix}{opt_text}')
            else:
                # Continuation of previous option if it was multi-line
                if options:
                    options[-1] += ' ' + opt_line
                
        # Format the question number with leading zero if single digit
        try:
            q_num_padded = f'{int(q_num):02d}'
        except ValueError:
            q_num_padded = q_num
                
        gift = f'// {q_label}\n::P{q_num_padded}::{stem} {{\n'
        for opt in options:
            gift += f'{opt}\n'
        gift += '}\n'
        gift_lines.append(gift)

    try:
        with open(output_txt_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(gift_lines))
        logger.info(f"Successfully created {output_txt_path} with {len(gift_lines)} questions.")
        return True
    except Exception as e:
        logger.error(f"Failed to write GIFT file {output_txt_path}: {e}")
        return False


def _get_cmid_for_activity(driver, activity_name: str, wait_time: int) -> str:
    """Returns the cmid (course module ID) for a given activity name on the course page."""
    wait = WebDriverWait(driver, wait_time)
    try:
        activity_links = driver.find_elements(By.CSS_SELECTOR, "a.aalink, a.instancename")
        for link in activity_links:
            if activity_name.lower() in link.text.lower():
                href = link.get_attribute("href")
                if href:
                    m = re.search(r"id=(\d+)", href)
                    if m:
                        return m.group(1)
    except Exception as e:
        logger.error(f"Error finding activity '{activity_name}': {e}")
    return None


def import_gift_to_moodle(driver, course_id: int, week: str, txt_path: str, wait_time: int) -> bool:
    """
    Navigates to the Moodle course question bank,
    and imports the GIFT .txt file into its category.
    Always uses the direct import URL to avoid Moodle UI navigation issues.
    """
    wait = WebDriverWait(driver, wait_time)
    activity_name = f"{week} | Puntos extras"
    
    logger.info(f"Navigating directly to Import page for course {course_id}...")
    import_url = f"{Config.MOODLE_URL}/question/bank/importquestions/import.php?courseid={course_id}"
    driver.get(import_url)
    
    try:
        # Select the target category (e.g., "Semana 1")
        week_num = week.replace("S", "")
        category_name = f"Semana {week_num}"
        logger.info(f"  [{activity_name}] Selecting category: {category_name}...")
        
        # We can use selenium's Select class, but since the section might be collapsed,
        # we can execute a script to select the option containing the category name text.
        driver.execute_script(f"""
            var select = document.getElementById('id_category');
            if (select) {{
                for (var i = 0; i < select.options.length; i++) {{
                    var optText = select.options[i].text;
                    if (optText.includes('{category_name}') && !optText.includes('Por defecto') && !optText.includes('Superior')) {{
                        select.selectedIndex = i;
                        var event = new Event('change', {{ bubbles: true }});
                        select.dispatchEvent(event);
                        break;
                    }}
                }}
            }}
        """)
        
        # Select GIFT format
        logger.info(f"  [{activity_name}] Selecting GIFT format...")
        gift_radio = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='radio' and contains(@value, 'gift')]")))
        if not gift_radio.is_selected():
            driver.execute_script("arguments[0].click();", gift_radio)
            
        # Use the file picker
        logger.info(f"  [{activity_name}] Opening file picker...")
        choose_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[contains(@value, 'Seleccione un archivo')] | //button[contains(text(), 'Seleccione un archivo')] | //*[contains(text(), 'Choose a file')]")))
        driver.execute_script("arguments[0].click();", choose_btn)
        
        # Wait for modal and click 'Subir un archivo'
        logger.info(f"  [{activity_name}] Clicking 'Subir un archivo'...")
        upload_menu = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Subir un archivo') or contains(text(), 'Upload a file')]")))
        driver.execute_script("arguments[0].click();", upload_menu)
        
        # Send file path to hidden input
        logger.info(f"  [{activity_name}] Attaching file: {txt_path}...")
        file_input = wait.until(EC.presence_of_element_located((By.NAME, "repo_upload_file")))
        file_input.send_keys(os.path.abspath(txt_path))
        time.sleep(1)
        
        # Click "Subir este archivo"
        logger.info(f"  [{activity_name}] Clicking 'Subir este archivo'...")
        upload_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Subir este archivo') or contains(text(), 'Upload this file')]")))
        driver.execute_script("arguments[0].click();", upload_btn)
        
        # Wait for modal to close and file to be attached
        time.sleep(2)
        
        # Submit the import form
        logger.info(f"  [{activity_name}] Submitting import form...")
        submit_btn = wait.until(EC.element_to_be_clickable((By.ID, "id_submitbutton")))
        driver.execute_script("arguments[0].click();", submit_btn)
        
        # Wait for the "Continuar" button to confirm success
        logger.info(f"  [{activity_name}] Waiting for 'Continuar' confirmation...")
        continue_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Continuar') or contains(text(), 'Continue')]")))
        driver.execute_script("arguments[0].click();", continue_btn)
        
        logger.info(f"Successfully imported GIFT questions into {activity_name}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to import GIFT file for {activity_name}: {e}")
        return False


def add_questions_to_quiz(driver, course_id: int, week: str, wait_time: int) -> bool:
    """
    Navigates to the Edit Quiz page for 'SX | Puntos extras' and adds
    the newly imported questions from the question bank.
    """
    wait = WebDriverWait(driver, wait_time)
    activity_name = f"{week} | Puntos extras"
    
    logger.info(f"Navigating to Edit Quiz page for {activity_name}")
    navigate_to_course(driver, Config.MOODLE_URL, course_id, wait_time)
    
    cmid = _get_cmid_for_activity(driver, activity_name, wait_time)
    if not cmid:
        return False
        
    # Direct URL to edit the quiz
    edit_quiz_url = f"{Config.MOODLE_URL}/mod/quiz/edit.php?cmid={cmid}"
    driver.get(edit_quiz_url)
    
    try:
        # Check if questions are already added (quiz might already have them)
        existing_questions = driver.find_elements(By.CSS_SELECTOR, "li.slot")
        if len(existing_questions) > 0:
            logger.info(f"{activity_name} already contains {len(existing_questions)} questions. Skipping add.")
            return True
            
        # Click "Agregar" (Add)
        add_menus = driver.find_elements(By.CSS_SELECTOR, "div.add-menu-outer a[data-action='addmenu']")
        if not add_menus:
            # Maybe there's a different button in other themes
            add_menus = driver.find_elements(By.XPATH, "//a[contains(text(), 'Agregar') or contains(text(), 'Add')]")
            
        if add_menus:
            # Click the last "Agregar" menu (usually the one at the bottom adds to the end)
            driver.execute_script("arguments[0].click();", add_menus[-1])
            time.sleep(1)
            
            # Click "del banco de preguntas" (from question bank)
            from_bank = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@data-action, 'addquestionbank') or contains(text(), 'banco de preguntas') or contains(text(), 'from question bank')]")))
            driver.execute_script("arguments[0].click();", from_bank)
            
            # Wait for the modal/page to load
            time.sleep(2)
            
            # Select all questions checkbox
            select_all = wait.until(EC.element_to_be_clickable((By.ID, "cbqb")))
            if not select_all.is_selected():
                driver.execute_script("arguments[0].click();", select_all)
                
            # Click "Añadir preguntas seleccionadas al cuestionario"
            add_selected_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@type='submit' and contains(@value, 'cuestionario')] | //input[@type='submit' and contains(@value, 'selected')]")))
            driver.execute_script("arguments[0].click();", add_selected_btn)
            
            # Wait for reload
            time.sleep(2)
            logger.info(f"Successfully added questions to {activity_name} quiz.")
            return True
        else:
            logger.warning(f"Could not find 'Agregar' menu for {activity_name}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to add questions to {activity_name} quiz: {e}")
        return False


def clear_puntos_extras_questions(driver, course_id: int, wait_time: int = 10):
    """
    Clears out existing questions from each week's 'Semana X' Question Bank category
    before the import process.
    """
    wait = WebDriverWait(driver, wait_time)
    logger.info(f"Navigating to Question Bank for course {course_id} to clear existing questions.")
    
    # Go to the Question Bank root
    bank_url = f"{Config.MOODLE_URL}/question/edit.php?courseid={course_id}"
    driver.get(bank_url)
    
    for week in PUNTOS_WEEKS:
        try:
            week_num = week.replace("S", "")
            category_name = f"Semana {week_num}"
            logger.info(f"Attempting to clear questions for {category_name}...")
            
            # Robust category selection via URL filtering
            try:
                # Wait for the category select or autocomplete to be present before extracting
                wait.until(EC.presence_of_element_located((By.XPATH, "//select[contains(@name, 'category')] | //ul[contains(@class, 'form-autocomplete-suggestions')]")))
                time.sleep(1) # Small buffer for Moodle AMD initialization
                
                # 1. Extract the exact category value from the DOM
                cat_val = driver.execute_script(f"""
                    var val = null;
                    // Try the autocomplete suggestions first
                    var lis = document.querySelectorAll('.form-autocomplete-suggestions li[role="option"]');
                    for (var i = 0; i < lis.length; i++) {{
                        var optText = lis[i].innerText || lis[i].textContent;
                        if (optText.includes('Semana {week_num}') && !optText.includes('Por defecto') && !optText.includes('Superior')) {{
                            val = lis[i].getAttribute('data-value');
                            break;
                        }}
                    }}
                    
                    // Fallback to the hidden select
                    if (!val) {{
                        var select = document.querySelector('select[name="filter[category][values][]"]') || document.querySelector('select[name="category"]') || document.getElementById('id_category');
                        if (select) {{
                            for (var i = 0; i < select.options.length; i++) {{
                                var optText = select.options[i].text;
                                if (optText.includes('Semana {week_num}') && !optText.includes('Por defecto') && !optText.includes('Superior')) {{
                                    val = select.options[i].value;
                                    break;
                                }}
                            }}
                        }}
                    }}
                    return val;
                """)
                
                if cat_val:
                    logger.info(f"Found category value '{cat_val}' for {category_name}. Filtering via URL...")
                    
                    # Normalize category ID (Moodle 3 uses ID,CONTEXTID, Moodle 4 uses just ID)
                    cat_id = str(cat_val).split(',')[0]
                    
                    # Construct Moodle 4 JSON filter parameter
                    import json
                    import urllib.parse
                    filter_obj = {
                        "category": {
                            "jointype": 1,
                            "values": [cat_id],
                            "filteroptions": {"includesubcategories": "0"}
                        },
                        "hidden": {
                            "jointype": 1,
                            "values": [0]
                        }
                    }
                    filter_encoded = urllib.parse.quote(json.dumps(filter_obj))
                    
                    # We MUST ONLY use the filter parameter, passing 'cat=' alongside it causes 'question/invalidcategory' error in Moodle 4
                    filter_url = f"{Config.MOODLE_URL}/question/edit.php?courseid={course_id}&filter={filter_encoded}"
                    driver.get(filter_url)
                    
                    # Wait for the questions table to load
                    time.sleep(3)
                else:
                    logger.warning(f"Could not extract category value for {category_name}. Filter might fail.")
                    time.sleep(2)
            except Exception as e:
                logger.error(f"Error during category value extraction for {category_name}: {e}")
                time.sleep(2)
            
            # 2. Check if there are questions by looking for the header checkbox and at least one question checkbox
            try:
                check_all = driver.find_element(By.ID, "qbheadercheckbox")
                # Ensure there are individual question checkboxes available to select
                question_cbs = driver.find_elements(By.XPATH, "//input[@type='checkbox' and not(@id='qbheadercheckbox') and not(contains(@id, 'filter'))]")
                if not question_cbs:
                    logger.info(f"No questions found for {category_name}. Skipping delete.")
                    continue
            except Exception:
                logger.info(f"No questions table found for {category_name}. Skipping delete.")
                continue
            # 3. Click the 'Seleccionar todos' checkbox
            check_all = wait.until(EC.element_to_be_clickable((By.ID, "qbheadercheckbox")))
            if not check_all.is_selected():
                driver.execute_script("arguments[0].click();", check_all)
            time.sleep(1)
            
            # 4. Click 'Con seleccionadas' (With selected)
            bulk_selector = wait.until(EC.element_to_be_clickable((By.ID, "bulkactionsui-selector")))
            driver.execute_script("arguments[0].click();", bulk_selector)
            time.sleep(1)
            
            # 5. Click 'Borrar'
            delete_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@type='submit' and @name='deleteselected'] | //input[@value='Borrar' or @value='Delete'] | //button[contains(text(), 'Borrar') or contains(text(), 'Delete')]")))
            driver.execute_script("arguments[0].click();", delete_btn)
            
            # 6. Wait for confirmation page and confirm deletion
            logger.info(f"Confirming deletion for {category_name}...")
            confirm_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@type='submit' and (@value='Borrar' or @value='Delete' or contains(@class, 'btn-primary'))] | //button[contains(text(), 'Borrar') or contains(text(), 'Delete')]")))
            driver.execute_script("arguments[0].click();", confirm_btn)
            
            time.sleep(3)
            logger.info(f"Successfully cleared questions for {category_name}.")
            
        except Exception as e:
            logger.error(f"Error clearing questions for {week}: {e}")
            driver.get(bank_url)

    logger.info("Finished clearing existing questions.")

def run_puntos_extras_workflow(driver, course_id: int, wait_time: int = 10):
    """
    Main entry point for the Puntos Extras workflow.
    Iterates over S1-S8, converts DOCX to GIFT, and uploads them to Moodle.
    """
    logger.info(f"Starting Puntos Extras workflow for course {course_id}...")
    base_dir = os.path.join("assets", str(course_id), "evaluacion")
    
    weeks_to_import = []
    
    for week in PUNTOS_WEEKS:
        docx_path = os.path.join(base_dir, f"Puntos extra_{week}.docx")
        txt_path = os.path.join(base_dir, f"Puntos extra_{week}.txt")
        
        if not os.path.exists(docx_path):
            logger.warning(f"File not found: {docx_path}. Skipping.")
            continue
            
        # 1. Convert DOCX to GIFT
        success_conv = convert_docx_to_gift(docx_path, txt_path)
        if success_conv:
            weeks_to_import.append((week, txt_path))
            
    if not driver or not weeks_to_import:
        return
        
    # Phase 1: Import GIFT into Question Bank sequentially
    logger.info("Starting sequential import of questions...")
    imported_weeks = []
    
    for week, txt_path in weeks_to_import:
        success_import = import_gift_to_moodle(driver, course_id, week, txt_path, wait_time)
        if success_import:
            imported_weeks.append(week)
            
    # Phase 2: Add to Quiz sequentially
    if imported_weeks:
        logger.info("Starting sequential addition of questions to quizzes...")
        for week in imported_weeks:
            add_questions_to_quiz(driver, course_id, week, wait_time)
            
    logger.info("Puntos Extras workflow completed.")
