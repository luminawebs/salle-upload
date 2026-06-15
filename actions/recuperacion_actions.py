"""
recuperacion_actions.py
-----------------------
Automates the process of converting local DOCX files to Moodle GIFT format
and uploading them to the "Examen de recuperación" quiz.
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

RECUPERACION_WEEKS = ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"]


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

    text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])

    # Split by 'Pregunta N'
    questions = re.split(r"(?i)^(Pregunta\s+(\d+))\s*$", text, flags=re.MULTILINE)

    if len(questions) < 3:
        logger.warning(f"No questions found in {docx_path} matching 'Pregunta N'")
        return False

    gift_lines = []

    # questions list structure: ['', 'Pregunta 1', '1', 'Body...', 'Pregunta 2', '2', 'Body...']
    for i in range(1, len(questions), 3):
        if i + 2 >= len(questions):
            break

        q_label = questions[i].strip()  # e.g., 'Pregunta 1'
        q_num = questions[i + 1].strip()  # e.g., '1'
        q_body = questions[i + 2].strip()

        # Match the start of the first option, which usually looks like =A., ~B., A., etc.
        match = re.search(r"^(=?[A-Da-d]\.\s*)", q_body, flags=re.MULTILINE)
        if not match:
            logger.warning(f"Could not find options for {q_label} in {docx_path}")
            continue

        stem = q_body[: match.start()].strip()
        options_text = q_body[match.start() :].strip()

        # Format options
        options = []
        for opt_line in options_text.split("\n"):
            opt_line = opt_line.strip()
            if not opt_line:
                continue

            # Match '=A. text', '~B. text', 'C. text', '= D. text', etc.
            opt_match = re.match(r"^(=?)\s*[A-Da-d]\.\s*(.*)$", opt_line)
            if opt_match:
                is_correct = opt_match.group(1) == "="
                opt_text = opt_match.group(2)
                prefix = "=" if is_correct else "~"
                options.append(f"\t{prefix}{opt_text}")
            else:
                # Continuation of previous option if it was multi-line
                if options:
                    options[-1] += " " + opt_line

        # Format the question number with leading zero if single digit
        try:
            q_num_padded = f"{int(q_num):02d}"
        except ValueError:
            q_num_padded = q_num

        gift = f"// {q_label}\n::P{q_num_padded}::{stem} {{\n"
        for opt in options:
            gift += f"{opt}\n"
        gift += "}\n"
        gift_lines.append(gift)

    try:
        with open(output_txt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(gift_lines))
        logger.info(
            f"Successfully created {output_txt_path} with {len(gift_lines)} questions."
        )
        return True
    except Exception as e:
        logger.error(f"Failed to write GIFT file {output_txt_path}: {e}")
        return False


def _get_cmid_for_activity(driver, activity_name: str, wait_time: int) -> str:
    """Returns the cmid (course module ID) for a given activity name on the course page."""
    wait = WebDriverWait(driver, wait_time)
    try:
        activity_links = driver.find_elements(
            By.CSS_SELECTOR, "a.aalink, a.instancename"
        )
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


def import_gift_to_moodle(
    driver, course_id: int, week: str, txt_path: str, wait_time: int
) -> bool:
    """
    Navigates to the Moodle course, finds the 'Examen de recuperación' quiz,
    and imports the GIFT .txt file into its question bank.
    """
    wait = WebDriverWait(driver, wait_time)
    activity_name = "Examen de recuperación"

    logger.info(
        f"Navigating to course {course_id} to import questions for {activity_name}"
    )
    navigate_to_course(driver, Config.MOODLE_URL, course_id, wait_time)

    cmid = _get_cmid_for_activity(driver, activity_name, wait_time)
    if not cmid:
        logger.warning(f"Could not find activity '{activity_name}' on the course page.")
        return False

    logger.info(f"Found {activity_name} with cmid: {cmid}. Proceeding to Import page.")

    # Direct URL to the import page for this specific quiz context
    import_url = f"{Config.MOODLE_URL}/question/bank/importquestions/import.php?courseid={course_id}&cmid={cmid}"
    driver.get(import_url)

    try:
        # Select GIFT format first
        logger.info(f"  [{activity_name}] Selecting GIFT format...")
        gift_radio = wait.until(
            EC.presence_of_element_located(
                (By.XPATH, "//input[@type='radio' and contains(@value, 'gift')]")
            )
        )
        if not gift_radio.is_selected():
            driver.execute_script("arguments[0].click();", gift_radio)
            time.sleep(1)  # Wait in case it triggers any UI updates

        # Select the target category: "Examen de recuperación"
        category_name = "Examen de recuperación"
        logger.info(f"  [{activity_name}] Selecting category: {category_name}...")

        # We use a JS script to select the option whose text includes "Examen de recuperación"
        # We MUST avoid "Por defecto en Examen de recuperación" and "Superior para Examen de recuperación"
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

        # Use the file picker
        logger.info(f"  [{activity_name}] Opening file picker...")
        choose_btn = wait.until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    "//input[contains(@value, 'Seleccione un archivo')] | //button[contains(text(), 'Seleccione un archivo')] | //*[contains(text(), 'Choose a file')]",
                )
            )
        )
        driver.execute_script("arguments[0].click();", choose_btn)

        # Wait for modal and click 'Subir un archivo'
        logger.info(f"  [{activity_name}] Clicking 'Subir un archivo'...")
        upload_menu = wait.until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    "//span[contains(text(), 'Subir un archivo') or contains(text(), 'Upload a file')]",
                )
            )
        )
        driver.execute_script("arguments[0].click();", upload_menu)

        # Send file path to hidden input
        logger.info(f"  [{activity_name}] Attaching file: {txt_path}...")
        file_input = wait.until(
            EC.presence_of_element_located((By.NAME, "repo_upload_file"))
        )
        file_input.send_keys(os.path.abspath(txt_path))
        time.sleep(1)

        # Click "Subir este archivo"
        logger.info(f"  [{activity_name}] Clicking 'Subir este archivo'...")
        upload_btn = wait.until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    "//button[contains(text(), 'Subir este archivo') or contains(text(), 'Upload this file')]",
                )
            )
        )
        driver.execute_script("arguments[0].click();", upload_btn)

        # Wait for modal to close and file to be attached
        time.sleep(2)

        # Submit the import form
        logger.info(f"  [{activity_name}] Submitting import form...")
        submit_btn = wait.until(EC.element_to_be_clickable((By.ID, "id_submitbutton")))
        driver.execute_script("arguments[0].click();", submit_btn)

        # Wait for the "Continuar" button to confirm success
        logger.info(f"  [{activity_name}] Waiting for 'Continuar' confirmation...")
        continue_btn = wait.until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    "//button[contains(text(), 'Continuar') or contains(text(), 'Continue')]",
                )
            )
        )
        driver.execute_script("arguments[0].click();", continue_btn)

        logger.info(f"Successfully imported GIFT questions into {activity_name}")
        return True

    except Exception as e:
        logger.error(f"Failed to import GIFT file for {activity_name}: {e}")
        return False


def add_questions_to_quiz(driver, course_id: int, wait_time: int) -> bool:
    """
    Navigates to the Edit Quiz page for 'Examen de recuperación' and adds
    the newly imported questions from the question bank.
    """
    wait = WebDriverWait(driver, wait_time)
    activity_name = "Examen de recuperación"

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
            logger.info(
                f"{activity_name} already contains {len(existing_questions)} questions. Skipping add."
            )
            return True

        # Click "Agregar" (Add)
        add_menus = driver.find_elements(
            By.CSS_SELECTOR, "div.add-menu-outer a[data-action='addmenu']"
        )
        if not add_menus:
            # Maybe there's a different button in other themes
            add_menus = driver.find_elements(
                By.XPATH, "//a[contains(text(), 'Agregar') or contains(text(), 'Add')]"
            )

        if add_menus:
            # Click the last "Agregar" menu (usually the one at the bottom adds to the end)
            driver.execute_script("arguments[0].click();", add_menus[-1])
            time.sleep(1)

            # Click "del banco de preguntas" (from question bank)
            from_bank = wait.until(
                EC.element_to_be_clickable(
                    (
                        By.XPATH,
                        "//a[contains(@data-action, 'addquestionbank') or contains(text(), 'banco de preguntas') or contains(text(), 'from question bank')]",
                    )
                )
            )
            driver.execute_script("arguments[0].click();", from_bank)

            # Wait for the modal/page to load
            time.sleep(2)

            # Select all questions checkbox
            select_all = wait.until(EC.element_to_be_clickable((By.ID, "cbqb")))
            if not select_all.is_selected():
                driver.execute_script("arguments[0].click();", select_all)

            # Click "Añadir preguntas seleccionadas al cuestionario"
            add_selected_btn = wait.until(
                EC.element_to_be_clickable(
                    (
                        By.XPATH,
                        "//input[@type='submit' and contains(@value, 'cuestionario')] | //input[@type='submit' and contains(@value, 'selected')]",
                    )
                )
            )
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


def run_recuperacion_export_workflow(driver, course_id: int, wait_time: int = 10):
    """
    Main entry point for the Recuperacion workflow.
    Iterates over S1-S8, converts DOCX to GIFT, and uploads them to Moodle.
    """
    import glob

    logger.info(f"Starting Recuperacion workflow for course {course_id}...")
    base_dir = os.path.join("assets", str(course_id), "evaluacion", "recuperacion")

    if not os.path.exists(base_dir):
        logger.warning(f"Directory not found: {base_dir}. Skipping.")
        return

    # Keep track of successfully imported weeks to add to quiz later
    imported_weeks = []

    for week in RECUPERACION_WEEKS:
        # Use glob to handle variations in filename like 'o' vs 'ó' vs 'o\u0301'
        search_pattern = os.path.join(base_dir, f"ExamenRecuperaci*n_{week}.docx")
        matches = glob.glob(search_pattern)

        if not matches:
            logger.warning(
                f"File not found for week {week} (pattern: {search_pattern}). Skipping."
            )
            continue

        docx_path = matches[0]
        txt_path = docx_path.replace(".docx", ".txt")

        # 1. Convert DOCX to GIFT
        success_conv = convert_docx_to_gift(docx_path, txt_path)
        if not success_conv:
            continue

        if not driver:
            continue

        # 2. Import GIFT into Question Bank
        success_import = import_gift_to_moodle(
            driver, course_id, week, txt_path, wait_time
        )
        if success_import:
            imported_weeks.append(week)

    # 3. Add to Quiz (all questions we imported)
    if imported_weeks and driver:
        # We run it once, because it's the same activity and all questions go to the same category
        # The add_questions_to_quiz logic selects all questions in the bank for that category
        logger.info(
            f"Adding all imported questions from weeks {imported_weeks} to the quiz..."
        )
        add_questions_to_quiz(driver, course_id, wait_time)

    logger.info("Recuperacion workflow completed.")
