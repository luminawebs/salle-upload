"""
actividad_recursos_actions.py
-----------------------------
Extracts bibliographic references (Recursos básicos y complementarios)
from raw Taller HTML files (S2, S4, S6, S8) and uploads them
to the course's central "Recursos de apoyo" Glossary.
"""

import logging
import os
import time
from bs4 import BeautifulSoup

from actions.moodle_actions import navigate_to_course
from actions.actividad_actions import _read_raw_html, parse_actividad_data
from actions.recursos_apoyo_actions import (
    extract_reference_data,
    generate_recurso_html,
    add_glossary_entry,
    get_unidad_for_week
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from config.settings import Config

logger = logging.getLogger(__name__)

ACTIVIDAD_WEEKS = ["S2", "S4", "S6", "S8"]

def _extract_references_from_html(html_text: str, only_with_links: bool = False):
    """
    Given the extracted resource HTML, parses it and returns
    a list of clean text strings (the individual references).
    If only_with_links is True, it will only extract text from tags
    that contain at least one <a> tag.
    """
    if not html_text:
        return []

    soup = BeautifulSoup(html_text, "html.parser")
    items = []

    # _sanitize_resource_html unwrapped lists, so each reference
    # should typically be in a <p> or just a top-level string.
    for tag in soup.find_all(["p", "li"]):
        # Skip if it's nested inside another p/li
        if tag.find_parent(["p", "li"]):
            continue

        a_tags = tag.find_all('a', href=True)
        if only_with_links and not a_tags:
            continue

        normalized_text = " ".join(tag.get_text(" ", strip=True).split())
        if not normalized_text:
            continue
            
        for a in a_tags:
            href = a['href']
            if href and href.startswith('http') and href not in normalized_text:
                normalized_text += f" {href}"
                break

        items.append(normalized_text)

    if items:
        return items

    # Fallback if no tags
    a_tags_fallback = soup.find_all('a', href=True)
    if only_with_links and not a_tags_fallback:
        return []

    fallback_text = " ".join(soup.get_text(" ", strip=True).split())
    if fallback_text:
        for a in a_tags_fallback:
            href = a['href']
            if href and href.startswith('http') and href not in fallback_text:
                fallback_text += f" {href}"
                break
        return [fallback_text]
    return []


def run_actividad_recursos_workflow(driver, course_id: int, wait_time: int = 10):
    """
    Iterates over S2, S4, S6, S8, extracts references, and uploads
    them to the "Recursos de apoyo" glossary.
    """
    logger.info(f"Starting Actividad Recursos Export workflow for course {course_id}...")
    wait = WebDriverWait(driver, wait_time)
    
    base_dir = os.path.join("assets", str(course_id), "actividades")
    template_path = os.path.join("assets", "templates", "recursos_apoyo.html")
    
    if not os.path.exists(template_path):
        logger.error(f"Template {template_path} not found. Skipping workflow.")
        return False

    all_items = []
    
    for week in ACTIVIDAD_WEEKS:
        raw_path = os.path.join(base_dir, f"Plantilla_Taller_{week}.html")
        if not os.path.exists(raw_path):
            logger.warning(f"  Raw file not found, skipping: {raw_path}")
            continue
            
        raw_html = _read_raw_html(raw_path)
        data = parse_actividad_data(raw_html)
        
        # Convert week string like "S2" to an integer 2
        try:
            week_num = int(week.replace("S", ""))
        except ValueError:
            week_num = 1
            
        unidad = get_unidad_for_week(week_num)
        
        items = []
        if data.get("recursos_basicos_html"):
            items.extend(_extract_references_from_html(data["recursos_basicos_html"]))
            
        if data.get("recursos_complementarios_html"):
            items.extend(_extract_references_from_html(data["recursos_complementarios_html"]))

        if data.get("indicaciones_html"):
            items.extend(_extract_references_from_html(data["indicaciones_html"], only_with_links=True))
            
        for item_text in items:
            # Clean up the text again and ignore placeholder/headers
            clean_item_text = " ".join(item_text.split())
            if clean_item_text and clean_item_text.lower() not in ["concepto", "concepto.", "concepto ", "individual", "colaborativa"]:
                all_items.append({"text": clean_item_text, "unidad": unidad, "week": week})

    # Deduplicate while preserving order
    clean_items = []
    seen = set()
    for item in all_items:
        if item["text"] not in seen:
            seen.add(item["text"])
            clean_items.append(item)
            
    if not clean_items:
        logger.info("No recursos items found to upload from Actividades.")
        return True

    logger.info(f"Found {len(clean_items)} unique items. Navigating to 'Recursos de apoyo' Glossary...")
    
    # Navigate to course page if needed
    if not driver:
        # For dry-run testing
        for item in clean_items:
            concepto, citation, url = extract_reference_data(item["text"])
            logger.info(f"[DRY RUN] {item['week']} ({item['unidad']}) -> {concepto}")
        return True

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
            f.write(f"\n--- Actividad Recursos (Course {course_id}) ---\n")
            for m in missing_url_items:
                f.write(f"{m}\n")
        logger.info(f"Logged {len(missing_url_items)} items with missing URLs to {log_file}")

    logger.info("=====================================================")
    logger.info(f"Actividad Recursos workflow complete.")
    logger.info(f"Total entries processed: {len(clean_items)}")
    logger.info(f"Successful uploads: {success_count}")
    logger.info(f"Failed uploads: {fail_count}")
    logger.info("=====================================================")
    
    return True
