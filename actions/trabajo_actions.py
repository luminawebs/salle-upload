"""
trabajo_actions.py
------------------
Parses local SX_Trabajo.html files (S3, S6, S8) and:
  1. Fills the trabajo.html template with the extracted data.
  2. Saves the result to assets/<course_id>/actividades-trabajo-final/SX_trabajo_output.html
  3. Uploads the generated HTML to the corresponding Moodle activity
     named "SX | Trabajo".

Reuses all HTML parsing/cleaning helpers from actividad_actions.py.
"""

import logging
import os
import re
import time

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

from config.settings import Config
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from html_generator.generate_html import wrap_bibliographic_title_in_bold

# Reuse all parsing helpers from actividad_actions
from actions.actividad_actions import (
    _read_raw_html,
    _decode_html_entities,
    _remove_section_header,
    _extract_indicaciones_html,
    _extract_section_between_headings,
    generate_actividad_html_file,
    _get_edit_url_global,
    _configure_actividad_availability,
    _configure_actividad_grading,
)
from core.wysiwyg_handler import inject_html_into_wysiwyg

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Workflow Configuration
# ──────────────────────────────────────────────────────────────────────────────

DEFAULT_EXPORT_CONFIGS = {
    "trabajo": {
        "weeks": ["S3", "S6", "S8"],
        "folder": "actividades-trabajo-final",
        "file_pattern": "{week}_Trabajo.html",
        "output_pattern": "{week}_trabajo_output.html",
        "moodle_suffix": "| Trabajo",
        "log_name": "Trabajo Final",
        "template": "trabajo.html",
    }
}



# ---------------------------------------------------------------------------
# Parser — mirrors parse_actividad_data but uses "Proyecto integrador" title
# ---------------------------------------------------------------------------

def parse_trabajo_data(raw_html: str) -> dict:
    """
    Parse a SX_Trabajo.html file and return a dict with the same keys as
    parse_actividad_data so that generate_actividad_html_file can be reused.
    """
    soup = BeautifulSoup(raw_html, "html.parser")
    norm = " ".join(soup.get_text(" ", strip=True).split())

    data = {
        "nombre_actividad": None,
        "descripcion": None,
        "indicaciones_html": None,
        "juzgar_html": None,
        "actuar_html": None,
        "devolucion_html": None,
        "tipo_actividad": None,
        "desarrollo_actividad": None,
        "consulta_materiales": None,
        "recursos_basicos_html": None,
        "recursos_complementarios_html": None,
        "forma_entrega_html": None,
        "rol_profesor": None,
    }

    # ── 1. Nombre de la actividad ─────────────────────────────────────────
    # Pattern: "Proyecto integrador. <Title>" or "Evidencia de aprendizaje. <Title>"
    m = re.search(
        r"((?:Proyecto\s+integrador|Evidencia\s+de\s+aprendizaje)[.\s]+.+?)\s+Descripci[oó]n\s*:",
        norm, re.IGNORECASE,
    )

    if m:
        raw_name = _decode_html_entities(m.group(1).strip())
        raw_name = re.sub(r"\s+\.", ".", raw_name, count=1)
        data["nombre_actividad"] = re.sub(r" {2,}", " ", raw_name)
        logger.info(f"  -> nombre_actividad: {data['nombre_actividad']}")
    else:
        logger.warning("  -> nombre_actividad NOT found")

    # ── 2. Descripcion ───────────────────────────────────────────────────
    data["descripcion_html"] = _extract_section_between_headings(
        soup,
        r"Descripci[oó]n\s*:",
        [r"Indicaciones\s+del\s+desarrollo", r"Ver\s*:"],
        keep_lists=True,
    )
    if data.get("descripcion_html"):
        data["descripcion_html"] = _remove_section_header(data["descripcion_html"])
        logger.info("  -> descripcion_html extracted successfully")

    # ── 3. Indicaciones del desarrollo ──────────────────────────────────
    data["indicaciones_html"] = _extract_section_between_headings(
        soup,
        r"Indicaciones\s+del\s+desarrollo",
        [r"Tiempos\s+y\s+recursos", r"Rol\s+del\s+(?:profesor|tutor)", r"R[uú]brica"],
        keep_lists=True,
        keep_tables=True,
    )
    if not data["indicaciones_html"]:
        data["indicaciones_html"] = _extract_indicaciones_html(soup)

    # Trabajo files don't have Juzgar/Actuar/Devolucion sections
    data["juzgar_html"] = None
    data["actuar_html"] = None
    data["devolucion_html"] = None

    # ── 4. Tiempos ───────────────────────────────────────────────────────
    m = re.search(
        r"Tipo\s+de\s+actividad\s+([A-Za-z\u00C0-\u024F][^\n]{1,40}?)"
        r"(?:\s{2,}|\s+Tiempos|\s+Recursos)",
        norm, re.IGNORECASE,
    )
    if m:
        data["tipo_actividad"] = re.sub(r" {2,}", " ", _decode_html_entities(m.group(1).strip()))

    m = re.search(
        r"Desarrollo\s+de\s+la\s+actividad\s*:\s*(\d+)[º°]?\s*(horas?)",
        norm, re.IGNORECASE,
    )
    if m:
        data["desarrollo_actividad"] = f"{m.group(1)} {m.group(2)}"

    m = re.search(
        r"Consulta\s+de\s+materiales\s*:\s*(\d+)[º°]?\s*(horas?)", norm, re.IGNORECASE,
    )
    if m:
        data["consulta_materiales"] = f"{m.group(1)} {m.group(2)}"

    # ── 5. Recursos ──────────────────────────────────────────────────────
    data["recursos_basicos_html"] = _extract_section_between_headings(
        soup,
        r"Recurso\(?s?\)?\s*b[aá]sico\(?s?\)?\s*:",
        [
            r"Recurso\(?s?\)?\s*complementario\(?s?\)?\s*:",
            r"Rol\s+del\s+(?:profesor|tutor)\s*:",
            r"R[uú]brica\.\s*Proyecto",
        ],
    )

    data["recursos_complementarios_html"] = _extract_section_between_headings(
        soup,
        r"Recurso\(?s?\)?\s*complementario\(?s?\)?\s*:",
        [r"Rol\s+del\s+(?:profesor|tutor)\s*:", r"Forma\s+de\s+entrega", r"R[uú]brica\.\s*Proyecto"],
    )

    # ── 6. Forma de entrega ───────────────────────────────────────────────
    data["forma_entrega_html"] = _extract_section_between_headings(
        soup, r"Forma\s+de\s+entrega", [r"R[uú]brica\.\s*Proyecto"], keep_lists=True,
    )

    # ── 7. Rol del profesor ───────────────────────────────────────────────
    m = re.search(
        r"Rol\s+del\s+(?:profesor|tutor)\s*:\s*(?:Rol\s+del\s+(?:profesor|tutor)\s*:)?\s*(.+?)"
        r"\s*(?:Forma\s+de\s+entrega|R[uú]brica\.\s*Proyecto)",
        norm, re.IGNORECASE,
    )
    if m:
        data["rol_profesor"] = re.sub(r" {2,}", " ", _decode_html_entities(m.group(1).strip()))

    for key in [
        "indicaciones_html",
        "recursos_basicos_html",
        "recursos_complementarios_html",
        "forma_entrega_html",
    ]:
        if data.get(key):
            data[key] = _remove_section_header(data[key])
            if key in ["recursos_basicos_html", "recursos_complementarios_html"]:
                data[key] = wrap_bibliographic_title_in_bold(data[key])
            
            # Wrap evaluación with nolink span if not already wrapped
            data[key] = re.sub(r'(?i)(?<!<span class="nolink">)(evaluaci[oó]n)', r'<span class="nolink">\1</span>', data[key])

    return data


# ---------------------------------------------------------------------------
# Main workflow
# ---------------------------------------------------------------------------

def run_trabajo_export_workflow(driver, course_id: int, workflow_type: str = "trabajo", wait_time: int = 10):
    """
    Main entry point for Trabajo and Evidencia export workflows.
    """
    cfg = DEFAULT_EXPORT_CONFIGS.get(workflow_type)
    if not cfg:
        logger.error(f"Unknown export workflow type: {workflow_type}")
        return

    logger.info(f"Starting {cfg['log_name']} export workflow for course {course_id}...")
    base_dir = os.path.join("assets", str(course_id), cfg["folder"])
    if not os.path.exists(base_dir):
        # Fallback to just "trabajo" folder
        base_dir = os.path.join("assets", str(course_id), "trabajo")
    
    template_path = os.path.join("assets", "templates", cfg["template"])
    if not os.path.exists(template_path):
        logger.error(f"Template not found: {template_path}")
        return

    from actions.moodle_actions import navigate_to_course
    navigate_to_course(driver, Config.MOODLE_URL, course_id, wait_time)
    main_window = driver.current_window_handle

    # Wait for the course page to settle
    try:
        WebDriverWait(driver, 90).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "footer, #page-footer"))
        )
        logger.info("  Course page fully loaded (footer visible).")
    except Exception as e:
        logger.warning(f"  Wait for footer finished with: {e}")

    # ── Apply week filtering ──────────────────────────────────────────────────
    weeks_to_process = cfg["weeks"]
    if Config.TRABAJO_WEEKS_FILTER:
        filter_list = [w.strip().upper() for w in Config.TRABAJO_WEEKS_FILTER.split(",")]
        weeks_to_process = [w for w in weeks_to_process if w.upper() in filter_list]
        logger.info(f"  Filtering weeks by: {filter_list}. Remaining: {weeks_to_process}")

    if not weeks_to_process:
        logger.info(f"  No weeks left to process for {workflow_type} after filtering.")
        return

    for idx, week in enumerate(weeks_to_process):
        logger.info(f"--- Processing {cfg['log_name']} {week} ---")

        # Verify we're on the main course page before each week
        if idx > 0:
            try:
                # Switch back to main window if needed
                if len(driver.window_handles) > 1:
                    driver.switch_to.window(main_window)
                
                # Make sure we're still on the course page
                WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "footer, #page-footer, .course-content"))
                )
                logger.info(f"  Main course page verified for {week}")
                
                # CRITICAL: Wait for any pending AJAX/animations to complete
                time.sleep(3)  # Give Moodle time to stabilize
                
            except Exception as e:
                logger.warning(f"  Course page check failed: {e}. Attempting to re-navigate.")
                try:
                    navigate_to_course(driver, Config.MOODLE_URL, course_id, wait_time)
                    main_window = driver.current_window_handle
                except Exception as navigate_error:
                    logger.error(f"  Re-navigation failed: {navigate_error}")
                    continue

        raw_filename = cfg["file_pattern"].format(week=week)
        output_filename = cfg["output_pattern"].format(week=week)
        raw_path = os.path.join(base_dir, raw_filename)
        output_path = os.path.join(base_dir, output_filename)
        moodle_activity_name = f"{week} {cfg['moodle_suffix']}"

        try:
            if not os.path.exists(raw_path):
                logger.warning(f"  Raw file not found, skipping: {raw_path}")
                continue

            raw_html = _read_raw_html(raw_path)
            parsed_data = parse_trabajo_data(raw_html)

            # ── 1. Generate output HTML ───────────────────────────────────
            try:
                generate_actividad_html_file(parsed_data, template_path, output_path)
                logger.info(f"  Generated: {output_path}")
            except Exception as e:
                logger.error(f"  Failed to generate HTML for {week}: {e}")
                continue

            # ── 2. Upload to Moodle ───────────────────────────────────────
            try:
                # Add a small delay before searching for the activity
                time.sleep(2)
                
                upload_url = _get_edit_url_global(driver, moodle_activity_name)
                if not upload_url:
                    logger.warning(f"  Moodle activity '{moodle_activity_name}' not found. Skipping upload.")
                    continue

                driver.execute_script(f"window.open('{upload_url}', '_blank');")
                driver.switch_to.window(driver.window_handles[-1])

                with open(output_path, "r", encoding="utf-8") as f:
                    html_content = f.read()

                WebDriverWait(driver, wait_time).until(EC.presence_of_element_located((By.CSS_SELECTOR, "body")))
                
                # Configure the availability dates and grading before saving
                _configure_actividad_availability(driver)
                _configure_actividad_grading(driver)

                success = inject_html_into_wysiwyg(driver, html_content, wait_time)

                if success:
                    logger.info(f"  Successfully uploaded {week} {workflow_type} to Moodle.")
                else:
                    logger.error(f"  Upload failed for {week} {workflow_type}.")

                # Close the editor tab
                driver.close()
                driver.switch_to.window(main_window)
                
                # CRITICAL: Wait after closing tab and switching back
                # This gives Moodle time to refresh any cached content
                time.sleep(3)
                
                # Optional: Scroll to reset page position
                driver.execute_script("window.scrollTo(0, 0);")

            except Exception as e:
                logger.error(f"  Error during upload of {week}: {e}")
                try:
                    if len(driver.window_handles) > 1:
                        driver.close()
                    driver.switch_to.window(main_window)
                    # Wait after error recovery
                    time.sleep(2)
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"  Unexpected error processing {week}: {e}")
            try:
                driver.switch_to.window(main_window)
                time.sleep(2)
            except Exception:
                pass

    logger.info(f"{cfg['log_name']} export workflow complete.")