"""
actividad_rubrica_actions.py
────────────────────────────
Este módulo se encarga de automatizar la gestión de rúbricas de calificación en Moodle.

Funcionalidad principal:
1.  **Extracción (Parsing)**: Lee el archivo HTML de la plantilla del taller (`Plantilla_Taller_SX.html`) 
    ubicado en los activos del curso. Extrae la tabla de rúbrica, identificando criterios, 
    niveles de desempeño (descripciones) y puntajes numéricos.
2.  **Navegación**: Utiliza Selenium para navegar en Moodle hasta la actividad correspondiente 
    (ej. "S2 | Actividad"). 
3.  Accede a la sección de "Calificación avanzada" y busca el editor de rúbricas.
4.  **Automatización del Editor**: 
    - Crea dinámicamente las filas de criterios necesarias.
    - Interactúa con los campos de texto ocultos de Moodle (YUI editor) para inyectar las descripciones.
    - Configura los puntajes para cada nivel (Excelente, Bueno, etc.).
5.  **Persistencia**: Guarda la rúbrica configurada en la plataforma.

Estructura de la tabla esperada en el HTML:
- Fila 0: Encabezados (Criterios, niveles, puntos).
- Filas N: Nombre del criterio y descripciones de niveles (L1 a L5).
- Filas N+1: Puntajes asociados a los niveles anteriores.
"""
import logging
import os
import re
import time

from bs4 import BeautifulSoup
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    NoSuchElementException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from actions.moodle_actions import MoodleAutomation
from config.settings import Config


logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Workflow Configuration
# ──────────────────────────────────────────────────────────────────────────────

DEFAULT_CONFIGS = {
    "actividad": {
        "weeks": [{"label": "S2", "semana": 2}, {"label": "S4", "semana": 4}, {"label": "S6", "semana": 6}, {"label": "S8", "semana": 8}],
        "folder": "actividades",
        "file_pattern": "Plantilla_Taller_{label}.html",
        "moodle_suffix": "| Actividad",
        "log_name": "Actividad"
    },
    "trabajo": {
        "weeks": [{"label": "S3", "semana": 3}, {"label": "S6", "semana": 6}, {"label": "S8", "semana": 8}],
        "folder": "actividades-trabajo-final",
        "file_pattern": "{label}_Trabajo.html",
        "moodle_suffix": "| Trabajo",
        "log_name": "Trabajo Final"
    },
    "evidencia": {
        "weeks": [{"label": "S8", "semana": 8}],
        "folder": "actividades-trabajo-final",
        "file_pattern": "{label}_Evidencia.html",
        "moodle_suffix": "| Evidencia",
        "log_name": "Evidencia de Aprendizaje"
    }
}



# ──────────────────────────────────────────────────────────────────────────────
# Parser
# ──────────────────────────────────────────────────────────────────────────────

def _clean_text(text: str) -> str:
    """Replace all internal whitespace (newlines/tabs) with spaces and clean up weird bullets."""
    cleaned = re.sub(r'\s+', ' ', text).strip()
    cleaned = re.sub(r'[\ufffd\uf0b7]', '·', cleaned)
    return cleaned

def _format_cell_content(td) -> str:
    """
    Process a TD element: if it contains multiple items, format each item with 
    a '·' prefix and separate them with newlines. 
    Handles malformed nested HTML (like unclosed <li> tags) by only extracting text
    from leaf block elements to avoid text duplication.
    """
    # Unwrap common inline tags so their text merges properly
    for tag in td.find_all(["font", "span", "strong", "b", "i", "u", "em"]):
        tag.unwrap()
        
    items = []
    blocks = td.find_all(["p", "li", "div"])
    if blocks:
        for b in blocks:
            # Only process leaf blocks (no nested p/li/div) to avoid duplicating text
            if not b.find(["p", "li", "div"]):
                text = _clean_text(b.get_text(" ", strip=True))
                if text:
                    items.append(text)
    else:
        text = _clean_text(td.get_text(" ", strip=True))
        if text:
            items.append(text)
            
    # Filter out exact duplicates (sometimes MS Word HTML duplicates text)
    unique_items = []
    for item in items:
        if item not in unique_items:
            unique_items.append(item)
            
    if len(unique_items) > 1:
        # Note: We keep \n here ONLY to separate bullet points. 
        # This is safe because we use JS .value to set text, so it won't trigger Enter.
        return "\n".join([f"· {i.lstrip('·-•*').strip()}" for i in unique_items])
    elif len(unique_items) == 1:
        return unique_items[0].lstrip("·-•* ").strip()
        
    return ""


def parse_rubrica_from_html(html_path: str) -> list[dict]:
    """
    Parse the Rúbrica table from a Plantilla_Taller_SX.html file.

    Returns a list of criterion dicts:
        [{
            "name":   str,
            "levels": [str, str, str, str, str],   # L1..L5 descriptions
            "scores": [str, str, str, str, str],   # L1..L5 numeric scores
        }]
    """
    with open(html_path, encoding="utf-8", errors="replace") as f:
        soup = BeautifulSoup(f, "html.parser")

    tables = soup.find_all("table")
    if not tables:
        logger.warning(f"parse_rubrica: no tables found in {html_path}")
        return []

    # The rubric is always the last table in the document
    rubric_table = tables[-1]
    rows = rubric_table.find_all("tr")
    criteria = []
    i = 0

    while i < len(rows):
        row_tds = rows[i].find_all(["th", "td"])
        cells_text = [c.get_text(" ", strip=True) for c in row_tds]

        # Skip header row
        if i == 0:
            i += 1
            continue

        # Filter trailing empty cells to find the true length
        valid_cells = [c for c in cells_text if c.strip()]

        # Score rows or malformed rows — skip
        if len(valid_cells) < 6:
            i += 1
            continue

        if valid_cells[0].lower().strip() == "puntaje":
            i += 1
            continue

        # Cell 0 is the Criterion Name, Cells 1-5 are Levels
        crit_name = _clean_text(cells_text[0])
        levels = [_format_cell_content(row_tds[k]) for k in range(1, 6)]

        # Lookahead for score row
        scores = []
        if i + 1 < len(rows):
            score_tds = rows[i + 1].find_all(["th", "td"])
            sc_text = [c.get_text(" ", strip=True) for c in score_tds]
            valid_sc = [c for c in sc_text if c.strip()]
            
            if valid_sc and valid_sc[0].lower().strip() == "puntaje":
                scores = [sc_text[k].strip() for k in range(1, 6)]
                i += 2
            else:
                i += 1
        else:
            i += 1

        if crit_name:
            # Clean up scores: remove spaces and non-numeric characters (except dots)
            # e.g., "0 .7" -> "0.7", "1 puntos" -> "1"
            clean_scores = [re.sub(r"[^\d.]", "", s) for s in scores]
            criteria.append({"name": crit_name, "levels": levels, "scores": clean_scores})

    return criteria


# ──────────────────────────────────────────────────────────────────────────────
# Selenium helpers
# ──────────────────────────────────────────────────────────────────────────────

def _wait(driver, timeout=10):
    return WebDriverWait(driver, timeout)


def _click_js(driver, element):
    """Click via JavaScript — bypasses overlay issues."""
    driver.execute_script("arguments[0].click();", element)


def _set_textarea_value(driver, textarea, value: str, timeout: int = 8):
    """
    Reveal a hidden YUI textarea, clear it, type new value, then blur to commit.
    The rubric editor hides textareas with class 'hiddenelement'; clicking the
    adjacent .pseudotablink reveals them.
    """
    # If the textarea is hidden, click the pseudotablink to reveal it
    try:
        parent = textarea.find_element(By.XPATH, "..")  # definition div or description cell
        pseudolink = parent.find_element(By.CSS_SELECTOR, ".pseudotablink")
        _click_js(driver, pseudolink)
        time.sleep(0.3)
    except NoSuchElementException:
        pass

    _wait(driver, timeout).until(EC.visibility_of(textarea))
    textarea.clear()
    textarea.send_keys(value)
    # Trigger blur and change events via JS to ensure Moodle registers the change
    driver.execute_script("arguments[0].dispatchEvent(new Event('blur'));", textarea)
    driver.execute_script("arguments[0].dispatchEvent(new Event('change'));", textarea)
    textarea.send_keys(Keys.TAB)  # commit and move away
    time.sleep(0.2)


def _set_score_input(driver, score_input, value: str, timeout: int = 8):
    """
    Reveal and set a hidden score input field in the rubric editor.
    """
    try:
        wrapper = score_input.find_element(By.XPATH, "..")
        pseudolink = wrapper.find_element(By.CSS_SELECTOR, ".pseudotablink")
        _click_js(driver, pseudolink)
        time.sleep(0.3)
    except NoSuchElementException:
        pass

    _wait(driver, timeout).until(EC.visibility_of(score_input))
    score_input.clear()
    score_input.send_keys(value)
    # Trigger events for scores too
    driver.execute_script("arguments[0].dispatchEvent(new Event('blur'));", score_input)
    driver.execute_script("arguments[0].dispatchEvent(new Event('change'));", score_input)
    score_input.send_keys(Keys.TAB)
    time.sleep(0.2)


# ──────────────────────────────────────────────────────────────────────────────
# Core rubric fill logic
# ──────────────────────────────────────────────────────────────────────────────

def _get_criteria_rows(driver):
    return driver.find_elements(By.CSS_SELECTOR, "table.criteria tr.criterion")


def _add_criterion(driver):
    """Click 'Añadir criterio' and wait for the new row to appear."""
    before = len(_get_criteria_rows(driver))
    btn = driver.find_element(By.CSS_SELECTOR, "div.addcriterion input[type='submit']")
    _click_js(driver, btn)
    _wait(driver, 10).until(lambda d: len(_get_criteria_rows(d)) > before)
    time.sleep(0.5)


def _handle_delete_modal(driver):
    """Handle the Moodle YUI confirm modal that pops up when deleting a row/level."""
    try:
        # Wait up to 3 seconds for the modal 'Sí' / 'Yes' button
        confirm_btn = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.XPATH, "//div[contains(@class, 'moodle-dialogue') or @role='dialog']//button[contains(translate(text(), 'SÍ', 'sí'), 'sí') or contains(text(), 'Yes')]"))
        )
        _click_js(driver, confirm_btn)
    except Exception:
        # Fallback for native alerts
        try:
            driver.switch_to.alert.accept()
        except Exception:
            pass


def _delete_extra_criteria(driver, needed: int, wait_time: int):
    """Delete any criteria rows beyond the needed amount."""
    rows = _get_criteria_rows(driver)
    while len(rows) > needed:
        logger.info(f"    Deleting extra criterion row ({len(rows)} > {needed})")
        last_row = rows[-1]
        delete_btn = last_row.find_element(By.CSS_SELECTOR, "input[name$='[delete]'], button[title*='Eliminar']")
        _click_js(driver, delete_btn)
        
        _handle_delete_modal(driver)
        
        _wait(driver, wait_time).until(lambda d: len(_get_criteria_rows(d)) < len(rows))
        time.sleep(0.5)
        rows = _get_criteria_rows(driver)


def _delete_extra_levels(driver, row, crit_idx: int, needed_levels: int, wait_time: int):
    """Delete any levels beyond the needed amount for a specific criterion."""
    def get_visible_levels(d, idx):
        r = _get_criteria_rows(d)[idx]
        return [l for l in r.find_elements(By.CSS_SELECTOR, "td.level:not(.addlevel)") if l.is_displayed()]

    visible_levels = get_visible_levels(driver, crit_idx)
    while len(visible_levels) > needed_levels:
        logger.info(f"    Deleting extra level ({len(visible_levels)} > {needed_levels}) on criterion {crit_idx+1}")
        last_level = visible_levels[-1]
        delete_btn = last_level.find_element(By.CSS_SELECTOR, "input[name$='[delete]']")
        _click_js(driver, delete_btn)
        
        _handle_delete_modal(driver)
        
        _wait(driver, wait_time).until(
            lambda d: len(get_visible_levels(d, crit_idx)) < len(visible_levels)
        )
        time.sleep(0.5)
        visible_levels = get_visible_levels(driver, crit_idx)


def _ensure_levels_for_criterion(driver, crit_idx: int, needed_levels: int, wait_time: int):
    """Ensure a specific criterion row has the required number of visible levels."""
    def get_visible_levels(d, idx):
        row = _get_criteria_rows(d)[idx]
        return [l for l in row.find_elements(By.CSS_SELECTOR, "td.level:not(.addlevel)") if l.is_displayed()]

    visible_levels = get_visible_levels(driver, crit_idx)
    while len(visible_levels) < needed_levels:
        row = _get_criteria_rows(driver)[crit_idx]
        add_btn = row.find_element(
            By.CSS_SELECTOR, 
            "input[value='Añadir nivel'], button[value='Añadir nivel'], input[name$='[levels][addlevel]']"
        )
        _click_js(driver, add_btn)
        
        _wait(driver, wait_time).until(
            lambda d: len(get_visible_levels(d, crit_idx)) > len(visible_levels)
        )
        time.sleep(0.5)
        visible_levels = get_visible_levels(driver, crit_idx)


def fill_rubric(driver, criteria_list: list[dict], wait_time: int = 10, rubric_name: str = None):
    """
    Fill the Moodle rubric editor form with the supplied criteria data.

    Moodle's default rubric starts with 3 criteria.  We add rows as needed
    to reach len(criteria_list).  Level count is assumed to already be 5
    (matching the template defaults); we do NOT add/remove levels.
    """
    
    # ── Fill rubric name if provided and empty ────────────────────────────────
    if rubric_name:
        try:
            name_input = driver.find_element(By.CSS_SELECTOR, "input[name='name'], #id_name")
            if not name_input.get_attribute("value"):
                logger.info(f"    Setting rubric name to: {rubric_name}")
                name_input.clear()
                name_input.send_keys(rubric_name)
        except Exception as e:
            logger.warning(f"    Could not set rubric name: {e}")

    # ── Ensure correct number of criteria rows ────────────────────────────────
    current_rows = _get_criteria_rows(driver)
    needed = len(criteria_list)
    
    # Add if fewer
    while len(current_rows) < needed:
        logger.info(f"    Adding criterion row ({len(current_rows)} → {needed})")
        _add_criterion(driver)
        current_rows = _get_criteria_rows(driver)

    # Delete if more
    if len(current_rows) > needed:
        _delete_extra_criteria(driver, needed, wait_time)

    # ── Fill each criterion ───────────────────────────────────────────────────
    for idx, crit in enumerate(criteria_list):
        # Always re-fetch row to avoid stale element reference after DOM updates
        row = _get_criteria_rows(driver)[idx]
        row_id = row.get_attribute("id") or ""
        crit_id_match = re.search(r"rubric-criteria-([a-zA-Z0-9_-]+)", row_id)
        if not crit_id_match:
            logger.warning(f"    Could not extract criterion ID from row {idx} (ID: '{row_id}')")
            continue
        crit_id = crit_id_match.group(1)
        logger.info(f"    Filling criterion {idx+1}: {crit['name'][:60]}")

        # Description textarea
        try:
            desc_ta_plain = driver.find_element(
                By.CSS_SELECTOR,
                f"td#rubric-criteria-{crit_id}-description-cell div.plainvalue"
            )
            _click_js(driver, desc_ta_plain)
            time.sleep(0.3)
            ta = driver.find_element(
                By.ID, f"rubric-criteria-{crit_id}-description"
            )
            _wait(driver, wait_time).until(EC.visibility_of(ta))
            # Use JS to set value to prevent newlines (\n) from triggering Moodle's 'Enter' save event
            driver.execute_script("arguments[0].value = arguments[1];", ta, crit["name"])
            driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", ta)
            driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", ta)
            driver.execute_script("arguments[0].dispatchEvent(new Event('blur', { bubbles: true }));", ta)
            time.sleep(0.3)
        except Exception as e:
            logger.warning(f"    Could not set criterion description: {e}")

        # Levels
        # Ensure the row has exactly the needed levels (add or delete as necessary)
        needed_levels = len(crit["levels"])
        _ensure_levels_for_criterion(driver, idx, needed_levels, wait_time)
        
        row = _get_criteria_rows(driver)[idx]
        _delete_extra_levels(driver, row, idx, needed_levels, wait_time)
        
        # Re-fetch row after modifying levels
        row = _get_criteria_rows(driver)[idx]
        all_level_tds = row.find_elements(By.CSS_SELECTOR, f"tr#rubric-criteria-{crit_id}-levels > td.level:not(.addlevel)")
        level_tds = [td for td in all_level_tds if td.is_displayed()]
        
        for li, level_td in enumerate(level_tds[:needed_levels]):
            lid_match = re.search(rf"rubric-criteria-{re.escape(crit_id)}-levels-([a-zA-Z0-9_-]+)", level_td.get_attribute("id") or "")
            if not lid_match:
                logger.warning(f"    Could not extract level ID for level {li} on criterion {idx}")
                continue
            lid = lid_match.group(1)

            # Level definition
            try:
                def_plain = level_td.find_element(By.CSS_SELECTOR, "div.definition div.plainvalue")
                _click_js(driver, def_plain)
                time.sleep(0.3)
                def_ta = driver.find_element(By.ID, f"rubric-criteria-{crit_id}-levels-{lid}-definition")
                _wait(driver, wait_time).until(EC.visibility_of(def_ta))
                
                text = crit["levels"][li] if li < len(crit["levels"]) else ""
                driver.execute_script("arguments[0].value = arguments[1];", def_ta, text)
                driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", def_ta)
                driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", def_ta)
                driver.execute_script("arguments[0].dispatchEvent(new Event('blur', { bubbles: true }));", def_ta)
                time.sleep(0.2)
            except Exception as e:
                logger.warning(f"    Could not set level {li+1} definition: {e}")

            # Score
            try:
                score_plain = level_td.find_element(By.CSS_SELECTOR, "div.score span.plainvalue")
                _click_js(driver, score_plain)
                time.sleep(0.3)
                score_inp = driver.find_element(
                    By.CSS_SELECTOR,
                    f"input[name='rubric[criteria][{crit_id}][levels][{lid}][score]']"
                )
                _wait(driver, wait_time).until(EC.visibility_of(score_inp))
                
                score_text = crit["scores"][li] if li < len(crit["scores"]) else "0"
                driver.execute_script("arguments[0].value = arguments[1];", score_inp, score_text)
                driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", score_inp)
                driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", score_inp)
                driver.execute_script("arguments[0].dispatchEvent(new Event('blur', { bubbles: true }));", score_inp)
                time.sleep(0.2)
            except Exception as e:
                logger.warning(f"    Could not set level {li+1} score: {e}")

    # ── Save ──────────────────────────────────────────────────────────────────
    try:
        # Give Moodle more time to register all blurred fields from the last criterion
        # Moodle's YUI/Atto can be very slow to sync the DOM
        logger.info("    Finalizing data entry, waiting for Moodle to sync...")
        time.sleep(3)
        
        # We strictly want the "Guardar" button to publish it.
        # In modern Moodle, 'saverubric' is publish, and 'saverubricdraft' is draft.
        save_selectors = [
            "input[name='saverubric']",       # Modern Moodle 'Guardar'
            "button[name='saverubric']",
            "input[name='saverubricsaved']",  # Older Moodle fallback
            "#id_saverubric"
        ]
        
        save_btn = None
        for selector in save_selectors:
            btns = driver.find_elements(By.CSS_SELECTOR, selector)
            for b in btns:
                if b.is_displayed() and b.is_enabled():
                    save_btn = b
                    logger.info(f"    ✓ Found active save button: {selector}")
                    break
            if save_btn:
                break
        
        if save_btn:
            logger.info("    Clicking Save button and waiting for 'Ready' status...")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", save_btn)
            time.sleep(1)
            try:
                # Use standard click to ensure all form submission events fire properly
                _wait(driver, 5).until(EC.element_to_be_clickable(save_btn))
                save_btn.click()
            except Exception as e:
                logger.warning(f"    Standard click failed, falling back to JS click: {e}")
                _click_js(driver, save_btn)
            
            # ── Wait for confirmation ─────────────────────────────────────────
            # After saving, Moodle returns to grading/manage.php. We want to see:
            # <span class="status ready">Listo para su uso</span>
            logger.info("    Monitoring Moodle for save confirmation...")
            
            def _save_confirmed(d):
                # Check for "Listo para su uso" / "Ready"
                ready_spans = d.find_elements(By.CSS_SELECTOR, "span.status.ready")
                for span in ready_spans:
                    text = span.text.lower()
                    if "listo" in text or "ready" in text:
                        return "ready_status"
                
                # Check for validation errors on the form (it didn't let us save)
                if d.find_elements(By.CSS_SELECTOR, ".error, .errormessage, span.error"):
                    # Check if we are still on the edit page with errors
                    if "rubric/edit.php" in d.current_url:
                        return "validation_error"
                
                return False

            try:
                result_type = _wait(driver, 20).until(_save_confirmed)
                
                if result_type == "ready_status":
                    logger.info("    ✓ STATUS CONFIRMED: Rúbrica lista para su uso.")
                    # Wait 5 seconds so the user can actually see it before we navigate away
                    logger.info("    Waiting 5 seconds to consolidate and allow visual verification...")
                    time.sleep(5)
                    return True
                elif result_type == "validation_error":
                    logger.error("    ✗ Form validation error preventing save. Still on editor page.")
                    return False
                    
            except TimeoutException:
                if "rubric/edit.php" not in driver.current_url:
                    logger.warning(f"    Navigated away but 'Ready' status not found. URL: {driver.current_url}")
                    time.sleep(4)
                    return True
                else:
                    logger.error("    ✗ Rubric save failed - still on editor page after 20s. Check for unhandled errors.")
                    return False
        else:
            logger.warning("    Could not find any visible and active save button.")
            return False
            
    except Exception as e:
        logger.error(f"    Critical error during save operation: {e}")
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Navigation helpers
# ──────────────────────────────────────────────────────────────────────────────

def _find_assign_url(driver, course_id: int, week_label: str, semana: int, moodle_suffix: str, wait_time: int) -> str | None:
    """
    Navigate to the course and find the assign activity named 'SX <suffix>'
    in Semana X.
    """
    from actions.moodle_actions import navigate_to_course

    week_name = f"Semana {semana}"
    moodle_name = f"{week_label} {moodle_suffix}"  # e.g. "S2 | Actividad"

    if "course/view.php" not in driver.current_url:
        navigate_to_course(driver, Config.MOODLE_URL, course_id, wait_time)

    # ── Wait for the course content to be fully loaded ──────────────────
    try:
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".course-content, #region-main"))
        )
        logger.info(f"  Course content loaded, waiting for sections to appear...")
    except TimeoutException:
        logger.warning(f"  Course content timeout, but continuing...")

    # ── Wait specifically for the section to exist before searching ──────
    section_xpath = (
        f"//li[contains(@class, 'section')]"
        f"[descendant::*[contains(@class, 'sectionname') or self::h3 or self::h4]"
        f"[contains(translate(., 'SEMANA', 'semana'), '{week_name.lower()}')]]"
    )
    
    try:
        section_li = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.XPATH, section_xpath))
        )
        logger.info(f"  ✓ Section '{week_name}' found")
        
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", section_li)
        time.sleep(1)
        
    except TimeoutException:
        logger.warning(f"  Section '{week_name}' not found by sectionname XPath after 30s.")
        fallback_xpath = f"//li[contains(@class, 'section')]//*[contains(text(), '{week_name}')]"
        try:
            section_li = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.XPATH, fallback_xpath))
            )
            section_li = section_li.find_element(By.XPATH, "./ancestor::li[contains(@class, 'section')]")
            logger.info(f"  ✓ Section '{week_name}' found via fallback XPath")
        except TimeoutException:
            logger.warning(f"  Section '{week_name}' not found. Course might not have this week.")
            return None

    # ── Find the assign activity by display name with flexible whitespace ──
    # IMPORTANT: Normalize whitespace by replacing multiple spaces with a single space
    # for comparison, but keep the search flexible
    
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(0.5)
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", section_li)
            time.sleep(1)
            
            # Get ALL activities in this section first
            activities = section_li.find_elements(By.XPATH, ".//li[contains(@class, 'activity')]")
            logger.info(f"  Found {len(activities)} activities in section '{week_name}'")
            
            found_activity = None
            found_href = None
            
            for activity in activities:
                try:
                    # Try to find the instance name
                    name_elem = activity.find_element(By.XPATH, ".//*[contains(@class, 'instancename')]")
                    name_text = name_elem.text.strip() if name_elem.text else name_elem.get_attribute("innerText")
                    
                    if name_text:
                        # Normalize whitespace for comparison (replace multiple spaces with single space)
                        normalized_name = ' '.join(name_text.split())
                        normalized_search = ' '.join(moodle_name.split())
                        
                        logger.debug(f"    Checking activity: '{normalized_name}' against '{normalized_search}'")
                        
                        if normalized_search.lower() in normalized_name.lower():
                            found_activity = activity
                            logger.info(f"  ✓ Found matching activity: '{normalized_name}'")
                            break
                except Exception as e:
                    continue
            
            if found_activity:
                # Find the primary link — must be mod/assign
                for link in found_activity.find_elements(By.CSS_SELECTOR, "a.aalink, a.instancename"):
                    href = link.get_attribute("href") or ""
                    if "mod/assign" in href:
                        if href.startswith("/"):
                            base = re.match(r"(https?://[^/]+)", Config.MOODLE_URL).group(1)
                            href = base + href
                        logger.info(f"  ✓ Found activity URL: {href}")
                        return href
                logger.warning(f"  Found '{moodle_name}' but no mod/assign URL in its links.")
                return None
                
        except Exception as e:
            if attempt < max_attempts - 1:
                logger.warning(f"  Attempt {attempt + 1}/{max_attempts} failed: {e}, retrying...")
                time.sleep(2)
            else:
                logger.warning(f"  Activity '{moodle_name}' not found after {max_attempts} attempts")
                return None

    return None


def _navigate_to_rubric_editor(driver, assign_url: str, wait_time: int) -> bool:
    """
    From a mod/assign activity URL (containing ?id=<cmid>), navigate to:
      grade/grading/manage.php?component=mod_assign&area=submissions&cmid=<cmid>
    Then:
      - If a rubric is already defined  → find and follow the 'Editar' rubric/edit.php link
      - If grading method not set yet   → look for 'Rubric' option and click it, then Edit
    Returns True if the rubric editor page loaded successfully.

    NOTE: Uses driver.page_source + BeautifulSoup for all link scanning to avoid
    stale element reference errors caused by the Moodle page re-rendering after load.
    """
    from selenium.common.exceptions import WebDriverException
    from bs4 import BeautifulSoup

    m = re.search(r"[?&]id=(\d+)", assign_url)
    if not m:
        logger.warning(f"  Could not extract cmid from URL: {assign_url}")
        return False
    cmid = m.group(1)
    base = re.match(r"(https?://[^/]+)", assign_url).group(1)

    # ── Step 2: Actually navigate to the activity page first ──────────────────
    # Visiting the activity page establishes the necessary context in Moodle.
    logger.info(f"  Navigating to activity page: {assign_url}")
    try:
        driver.get(assign_url)
        WebDriverWait(driver, wait_time).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#region-main, .region-main"))
        )
        # Brief pause to ensure Moodle registers the session context for this activity
        time.sleep(2)
    except WebDriverException as e:
        logger.error(f"  Error navigating to activity page: {e}")
        return False

    # ── Step 2b: Try to find 'Calificación avanzada' link on the activity page ───
    # Clicking the link is more reliable than direct URL navigation for context.
    logger.info("  Searching for 'Calificación avanzada' link on activity page...")
    link_clicked = False
    try:
        page_soup = BeautifulSoup(driver.page_source, "html.parser")
        advanced_grading_link = None
        for a in page_soup.find_all("a", href=True):
            text = a.get_text(" ", strip=True).lower()
            href = a.get("href", "")
            if "grading/manage.php" in href and ("calificación avanzada" in text or "advanced grading" in text or "gestión de calificaciones" in text):
                advanced_grading_link = href
                if advanced_grading_link.startswith("/"):
                    advanced_grading_link = base + advanced_grading_link
                break
        
        if advanced_grading_link:
            logger.info(f"  ✓ Found link on page: {advanced_grading_link}. Clicking...")
            driver.get(advanced_grading_link)
            # Wait for the page to load after the click
            WebDriverWait(driver, wait_time).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            time.sleep(1)
            link_clicked = True
    except Exception as e:
        logger.warning(f"  Could not find or click advanced grading link via UI: {e}")

    # ── Step 3: Navigate to grading management page (Fallback/Ensure) ──────────
    # We only force navigation if we didn't click a link OR if we are still not on a grading page
    if not link_clicked or "grading/manage.php" not in driver.current_url:
        manage_url = (
            f"{base}/grade/grading/manage.php"
            f"?component=mod_assign&area=submissions&cmid={cmid}"
        )
        logger.info(f"  Ensuring we are on grading manage URL: {manage_url}")
        try:
            driver.get(manage_url)
        except WebDriverException as e:
            logger.error(f"  WebDriver error navigating to manage page: {e}")
            return False
    else:
        logger.info(f"  Successfully reached grading page via UI link: {driver.current_url}")

    # ── Wait for page to fully load or error to appear ───────────────────────
    try:
        # We wait for either the main content region OR a Moodle error indicator
        # to appear, so we don't waste time waiting for the full timeout on error pages.
        def _content_or_error_found(d):
            # Check for success indicators
            if d.execute_script("return document.readyState") == "complete":
                if d.find_elements(By.CSS_SELECTOR, "#region-main, .region-main"):
                    return "success"
            
            # Check for error indicators
            title = d.title.lower()
            if "error" in title or "exception" in title:
                return "error_page"
            
            if d.find_elements(By.CSS_SELECTOR, ".alert-danger, .errormessage, .moodle-exception"):
                return "error_msg"
            
            return False

        wait_result = WebDriverWait(driver, wait_time).until(_content_or_error_found)
        
        if wait_result in ["error_page", "error_msg"]:
            logger.warning(f"  Moodle error detected early (type: {wait_result}).")
            # We continue to the BeautifulSoup parse to log the specific error text
        else:
            time.sleep(0.5)  # brief settle for dynamic content
            
    except (TimeoutException, WebDriverException) as e:
        if "target window already closed" in str(e):
            logger.error("  Browser window closed during page load.")
            return False
        logger.warning(f"  Page load monitoring timed out or failed: {e}")

    # ── Parse page source ONCE with BeautifulSoup (no stale elements) ─────────
    try:
        page_source = driver.page_source
        page_title = driver.title
    except WebDriverException as e:
        logger.error(f"  Cannot read page source — browser disconnected: {e}")
        return False

    soup = BeautifulSoup(page_source, "html.parser")
    logger.info(f"  Page title: {page_title}")

    # ── Check for Moodle error messages or access errors ─────────────────────
    error_msg = soup.find("div", class_="alert-danger") or soup.find("div", class_="errormessage")
    if error_msg:
        logger.warning(f"  Moodle error detected on manage page: {error_msg.get_text(strip=True)}")
        return False

    if "Error | Padre" in page_title or "error" in page_title.lower():
        logger.warning(f"  Access error to grading manage page for cmid {cmid}. Activity might not support advanced grading.")
        return False

    # Collect all links for diagnostics
    all_hrefs = [(a.get_text(" ", strip=True)[:60], a.get("href", ""))
                 for a in soup.find_all("a", href=True)]
    logger.info(f"  Links found on page ({len(all_hrefs)}):")
    for text, href in all_hrefs:
        logger.info(f"    [{text}] → {href}")

    # ── Case 1: Rubric already defined — find rubric/edit.php ─────────────────
    rubric_edit_url = next(
        (href for _, href in all_hrefs if "rubric/edit.php" in href),
        None
    )

    if rubric_edit_url:
        # Make absolute if relative
        if rubric_edit_url.startswith("/"):
            rubric_edit_url = base + rubric_edit_url
        logger.info(f"  ✓ Rubric editor URL found: {rubric_edit_url}")
        try:
            driver.get(rubric_edit_url)
            WebDriverWait(driver, wait_time).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            WebDriverWait(driver, wait_time).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#region-main, .region-main"))
            )
            time.sleep(1)
        except WebDriverException as e:
            logger.error(f"  Error loading rubric editor: {e}")
            return False
        return "rubric/edit.php" in driver.current_url

    # ── Case 2: Grading method not set — look for select dropdown or link ─────
    logger.info("  rubric/edit.php not found — checking for grading method selector...")
    
    # First, try Moodle 4.x select dropdown
    try:
        from selenium.webdriver.support.ui import Select
        select_elem = driver.find_element(By.CSS_SELECTOR, "select[name='setmethod']")
        sel = Select(select_elem)
        
        if sel.first_selected_option.get_attribute("value") != "rubric":
            logger.info("  Changing grading method to 'rubric' via select dropdown...")
            sel.select_by_value("rubric")
            
            # If there's a submit button right next to it (sometimes required if JS is slow)
            try:
                submit_btn = select_elem.find_element(By.XPATH, "./following-sibling::noscript//input[@type='submit']")
                submit_btn.click()
            except:
                pass
                
            WebDriverWait(driver, wait_time).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            time.sleep(1)
    except Exception as e:
        logger.info(f"  Select dropdown not used ({e}). Checking for links...")
        
        # Fallback to older Moodle link-based selection
        rubric_set_url = next(
            (href for text, href in all_hrefs
             if "setmethod=rubric" in href.lower() or
                ("grading" in href.lower() and "rubric" in href.lower()) or
                "calificación avanzada" in text[:30].lower()),
            None
        )

        if rubric_set_url:
            if rubric_set_url.startswith("/"):
                rubric_set_url = base + rubric_set_url
            logger.info(f"  Found 'set rubric method' link: {rubric_set_url}")
            try:
                driver.get(rubric_set_url)
                WebDriverWait(driver, wait_time).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
                time.sleep(1)
            except WebDriverException as e:
                logger.warning(f"  Error activating rubric method via link: {e}")
                
    # Re-parse source after potential activation
    try:
        page_source2 = driver.page_source
        soup2 = BeautifulSoup(page_source2, "html.parser")
        rubric_edit_url = next(
            (a.get("href", "") for a in soup2.find_all("a", href=True)
             if "rubric/edit.php" in a.get("href", "")),
            None
        )
        if rubric_edit_url:
            if rubric_edit_url.startswith("/"):
                rubric_edit_url = base + rubric_edit_url
            logger.info(f"  Rubric editor URL (after activation): {rubric_edit_url}")
            driver.get(rubric_edit_url)
            WebDriverWait(driver, wait_time).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            time.sleep(1)
            return "rubric/edit.php" in driver.current_url
    except Exception as e:
        logger.warning(f"  Failed to find rubric/edit.php after activation attempt: {e}")
    else:
        logger.warning(
            "  No rubric/edit.php link and no 'setmethod=rubric' link found. "
            "The activity may need 'Calificación avanzada' → 'Rúbrica' set in its settings."
        )

    return False




def _ensure_window_alive(driver) -> bool:
    """Check that the browser window is still open and responsive."""
    from selenium.common.exceptions import WebDriverException, NoSuchWindowException
    try:
        if driver is None:
            return False
        # Accessing window_handles is a standard check
        handles = driver.window_handles
        if not handles:
            return False
        # Accessing current_url ensures the session is still active
        _ = driver.current_url
        return True
    except (WebDriverException, NoSuchWindowException, Exception):
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Main workflow entry point
# ──────────────────────────────────────────────────────────────────────────────

def run_actividad_rubrica_workflow(driver, course_id: int, workflow_type: str = "actividad", wait_time: int = 10):
    """
    Generic rubric workflow for different activity types.
    """
    cfg = DEFAULT_CONFIGS.get(workflow_type)
    if not cfg:
        logger.error(f"Unknown rubric workflow type: {workflow_type}")
        return

    logger.info(f"Starting {cfg['log_name']} Rúbrica workflow for course {course_id}...")
    assets_dir = os.path.join("assets", str(course_id), cfg["folder"])

    # ── Apply week filtering ──────────────────────────────────────────────────
    weeks_to_process = cfg["weeks"]
    if Config.RUBRICA_WEEKS_FILTER:
        filter_list = [w.strip().upper() for w in Config.RUBRICA_WEEKS_FILTER.split(",")]
        weeks_to_process = [w for w in weeks_to_process if w["label"].upper() in filter_list]
        logger.info(f"  Filtering weeks by: {filter_list}. Remaining: {[w['label'] for w in weeks_to_process]}")

    if not weeks_to_process:
        logger.info(f"  No weeks left to process for {workflow_type} after filtering.")
        return

    total_ok = 0
    total_fail = 0

    for week in weeks_to_process:
        label = week["label"]
        semana = week["semana"]
        raw_filename = cfg["file_pattern"].format(label=label)
        raw_path = os.path.join(assets_dir, raw_filename)

        logger.info(f"--- Processing Rúbrica for {label} ({workflow_type}) ---")

        # Guard: make sure browser is still alive before each week
        if not _ensure_window_alive(driver):
            logger.error("  Browser window closed unexpectedly — aborting rúbrica workflow.")
            total_fail += len(weeks_to_process) - (weeks_to_process.index(week))
            break

        # ── Parse raw HTML ────────────────────────────────────────────────────
        if not os.path.exists(raw_path):
            logger.warning(f"  Raw file not found: {raw_path} — skipping {label}")
            total_fail += 1
            continue

        criteria = parse_rubrica_from_html(raw_path)
        if not criteria:
            logger.warning(f"  No criteria parsed from {raw_path} — skipping {label}")
            total_fail += 1
            continue

        logger.info(f"  Parsed {len(criteria)} criteria from {raw_path}")

        # ── Find activity on Moodle ───────────────────────────────────────────
        activity_url = _find_assign_url(driver, course_id, label, semana, cfg["moodle_suffix"], wait_time)
        if not activity_url:
            logger.warning(f"  Could not find '{label} {cfg['moodle_suffix']}' (mod/assign) in Semana {semana} — skipping {label}")
            total_fail += 1
            continue

        logger.info(f"  Activity URL: {activity_url}")

        # ── Navigate to rubric editor ─────────────────────────────────────────
        ok = _navigate_to_rubric_editor(driver, activity_url, wait_time)
        if not ok:
            logger.warning(f"  Could not open rubric editor for {label} — skipping")
            total_fail += 1
            continue

        # ── Fill rubric ───────────────────────────────────────────────────────
        try:
            ok = fill_rubric(driver, criteria, wait_time=wait_time, rubric_name=label)
            if ok:
                logger.info(f"  ✓ Rúbrica uploaded and confirmed for {label}")
                total_ok += 1
                
                # ── Explicitly navigate back to main course page ─────────────────
                from actions.moodle_actions import navigate_to_course
                logger.info(f"  Returning to main course page for course {course_id}...")
                navigate_to_course(driver, Config.MOODLE_URL, course_id, wait_time)
                time.sleep(2)
            else:
                logger.warning(f"  Rúbrica fill process returned False for {label}")
                total_fail += 1
        except Exception as e:
            logger.error(f"  Failed to fill rubric for {label}: {e}")
            total_fail += 1

    logger.info("=" * 55)
    logger.info(f"{cfg['log_name']} Rúbrica workflow complete.")
    logger.info(f"Successful: {total_ok}  |  Failed: {total_fail}")
    logger.info("=" * 55)

