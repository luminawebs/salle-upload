import copy
import logging
import os
import re
import time

from bs4 import BeautifulSoup, NavigableString
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

from config.settings import Config
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from html_generator.generate_html import wrap_bibliographic_title_in_bold

from actions.actividad_actions import (
    _read_raw_html,
    _decode_html_entities,
    _remove_section_header,
    _extract_section_between_headings,
    _get_edit_url_global,
    _configure_actividad_availability,
    _configure_actividad_grading,
)
from core.wysiwyg_handler import inject_html_into_wysiwyg

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Workflow Configuration
# ──────────────────────────────────────────────────────────────────────────────

DEFAULT_EXPORT_CONFIG = {
    "weeks": ["S8"],
    "folder": "actividades-trabajo-final",
    "file_pattern": "{week}_Evidencia.html",
    "output_pattern": "{week}_evidencia_output.html",
    "moodle_suffix": "| Evidencia",
    "log_name": "Evidencia de Aprendizaje",
    "template": "evidencia.html",
}

def parse_evidencia_data(raw_html: str) -> dict:
    """
    Parse a SX_Evidencia.html file and extract everything between
    'Descripción:' and 'Rúbrica'.
    """
    soup = BeautifulSoup(raw_html, "html.parser")
    
    data = {
        "indicaciones_html": None,
    }

    # Extract all content between Descripción: and Rúbrica
    # using keep_tables=True and keep_lists=True to preserve formatting
    data["indicaciones_html"] = _extract_section_between_headings(
        soup,
        r"Descripci[oó]n\s*:",
        [r"R[uú]brica"],
        keep_lists=True,
        keep_tables=True,
    )
    
    if data["indicaciones_html"]:
        data["indicaciones_html"] = _remove_section_header(data["indicaciones_html"])
        # Wrap bibliographic titles if any
        data["indicaciones_html"] = wrap_bibliographic_title_in_bold(data["indicaciones_html"])

    return data

def generate_evidencia_html_file(parsed_data: dict, template_path: str, output_path: str) -> None:
    """
    Reads evidencia.html template, injects the parsed HTML under the <h3>Evidencia</h3> tag,
    and removes the 'Lorem ipsum' paragraph.
    """
    with open(template_path, "r", encoding="utf-8") as f:
        template_html = f.read()

    soup = BeautifulSoup(template_html, "html.parser")

    evidencia_h3 = soup.find(lambda tag: tag.name == "h3" and "Evidencia" in tag.get_text())
    
    if evidencia_h3 and parsed_data.get("indicaciones_html"):
        # Remove the sibling <p> (Lorem ipsum)
        sib = evidencia_h3.find_next_sibling()
        if sib and sib.name == "p":
            sib.extract()
            
        # Inject the new parsed HTML content
        frag = BeautifulSoup(parsed_data["indicaciones_html"], "html.parser")
        insert_after = evidencia_h3
        for node in list(frag.contents):
            if isinstance(node, NavigableString) and not node.strip():
                continue
            clone = copy.deepcopy(node)
            insert_after.insert_after(clone)
            insert_after = clone

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(str(soup))


def run_evidencia_export_workflow(driver, course_id: int, wait_time: int = 10):
    """
    Main entry point for Evidencia export workflow.
    """
    cfg = DEFAULT_EXPORT_CONFIG

    logger.info(f"Starting {cfg['log_name']} export workflow for course {course_id}...")
    base_dir = os.path.join("assets", str(course_id), cfg["folder"])
    if not os.path.exists(base_dir):
        base_dir = os.path.join("assets", str(course_id), "trabajo")
    
    template_path = os.path.join("assets", "templates", cfg["template"])
    if not os.path.exists(template_path):
        logger.error(f"Template not found: {template_path}")
        return

    from actions.moodle_actions import navigate_to_course
    navigate_to_course(driver, Config.MOODLE_URL, course_id, wait_time)
    main_window = driver.current_window_handle

    try:
        WebDriverWait(driver, 90).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "footer, #page-footer"))
        )
        logger.info("  Course page fully loaded (footer visible).")
    except Exception as e:
        logger.warning(f"  Wait for footer finished with: {e}")

    weeks_to_process = cfg["weeks"]
    if Config.TRABAJO_WEEKS_FILTER:
        filter_list = [w.strip().upper() for w in Config.TRABAJO_WEEKS_FILTER.split(",")]
        weeks_to_process = [w for w in weeks_to_process if w.upper() in filter_list]

    if not weeks_to_process:
        logger.info(f"  No weeks left to process for Evidencia after filtering.")
        return

    for idx, week in enumerate(weeks_to_process):
        logger.info(f"--- Processing {cfg['log_name']} {week} ---")

        if idx > 0:
            try:
                if len(driver.window_handles) > 1:
                    driver.switch_to.window(main_window)
                
                WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "footer, #page-footer, .course-content"))
                )
                time.sleep(3)
                
            except Exception as e:
                try:
                    navigate_to_course(driver, Config.MOODLE_URL, course_id, wait_time)
                    main_window = driver.current_window_handle
                except Exception as navigate_error:
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
            parsed_data = parse_evidencia_data(raw_html)

            try:
                generate_evidencia_html_file(parsed_data, template_path, output_path)
                logger.info(f"  Generated: {output_path}")
            except Exception as e:
                logger.error(f"  Failed to generate HTML for {week}: {e}")
                continue

            try:
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
                    logger.info(f"  Successfully uploaded {week} Evidencia to Moodle.")
                else:
                    logger.error(f"  Upload failed for {week} Evidencia.")

                driver.close()
                driver.switch_to.window(main_window)
                time.sleep(3)
                driver.execute_script("window.scrollTo(0, 0);")

            except Exception as e:
                logger.error(f"  Error during upload of {week}: {e}")
                try:
                    if len(driver.window_handles) > 1:
                        driver.close()
                    driver.switch_to.window(main_window)
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
