import logging
import re
import time
import os
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

from actions.moodle_actions import navigate_to_course
from config.settings import Config
from core.wysiwyg_handler import inject_html_into_wysiwyg
from actions.docx_upload_actions import disable_multimedia_filter_for_activity
from actions.html_transformer import format_urls_in_html, format_typography_in_html

from core import progress

logger = logging.getLogger(__name__)

def add_etiqueta_materiales(driver, section_element, wait_time=10):
    wait = WebDriverWait(driver, wait_time)
    
    # Click 'Añadir una actividad o recurso'
    add_activity_btns = section_element.find_elements(By.CSS_SELECTOR, "button.activity-add, a.section-modchooser-link:not([data-action='addSection']), button.section-modchooser-link, [data-action='open-chooser']")
    if not add_activity_btns:
        logger.warning("Could not find 'Add activity' button.")
        return False
    add_activity_btn = add_activity_btns[-1]
    
    try:
        wait.until(EC.element_to_be_clickable(add_activity_btn)).click()
    except WebDriverException:
        driver.execute_script("arguments[0].click();", add_activity_btn)
        
    chooser = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".modchooser, .modal-dialog, .modal-content, [data-region='chooserdialogue']")))
    time.sleep(1)
    
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".modchooser .option, .modchooser .modchooser-item, .modal-dialog .option, .modal-dialog .modchooser-item, [data-region='chooserdialogue'] .option")))
    except TimeoutException:
        pass

    keywords = ["label", "etiqueta", "área de texto y medios", "texto y medios", "area de texto y medios"]
    options = chooser.find_elements(By.CSS_SELECTOR, ".option a, .option button, .option label, .modchooser-item, .option")
    
    found = False
    for option in options:
        text = option.text.lower()
        href = option.get_attribute("href") or ""
        data_name = option.get_attribute("data-name") or ""
        
        if any(k in text for k in keywords) or any(k in href for k in keywords) or any(k in data_name.lower() for k in keywords):
            if href and "javascript" not in href.lower():
                driver.get(href)
                found = True
                break
            else:
                try:
                    option.click()
                    found = True
                    break
                except WebDriverException:
                    driver.execute_script("arguments[0].click();", option)
                    found = True
                    break
                
    if not found:
        logger.warning("Could not find Label option in chooser.")
        return False
        
    try:
        wait.until(EC.presence_of_element_located((By.ID, "id_submitbutton2")))
    except Exception:
        pass
    video_html = '<p><video class="nomediaplugin" crossorigin="anonymous" autoplay="autoplay" loop="loop" muted="true">   <source src="https://unisallevirtual.lasalle.edu.co/multimedia/etiquetas/materialesdeestudio.mp4">   Materiales de Estudio.  </video></p>'
    
    success = inject_html_into_wysiwyg(driver, video_html, wait_time, target_section="intro")
    if not success: 
        return False
    # Wait for redirect back to course view
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "body.path-course-view")))
    except Exception:
        pass
        
    return True

def _reference_key(html: str) -> str:
    """The same reference written twice ("Plans , Business" / "Plans, Business"), as one key."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    text = re.sub(r"\s+([,.;:)])", r"\1", soup.get_text(" ").lower())
    # The links count too: the same text with another link is another reading.
    links = sorted(a.get("href", "") for a in soup.find_all("a"))
    return " ".join(text.split()).strip(" .") + "|" + " ".join(links)


# A number or dash typed at the start of a reference ("1. ", "2) ", "- ", "•"):
# the list's bullet replaces it, so the page doesn't show "• 1. Autor…".
_TYPED_MARKER_RE = re.compile(r"^\s*(?:\d{1,2}\s*[.)]|[-–—•·▪])\s*")


def _without_typed_marker(html: str) -> str:
    """The reference's HTML without a number or dash typed before its first word."""
    from bs4 import BeautifulSoup, NavigableString
    soup = BeautifulSoup(html, "html.parser")
    first = next((s for s in soup.find_all(string=True) if s.strip()), None)
    if isinstance(first, NavigableString) and _TYPED_MARKER_RE.match(first):
        first.replace_with(_TYPED_MARKER_RE.sub("", first, count=1))
    return str(soup)


def _only_a_link(tag) -> bool:
    """A paragraph that is just a link or a URL (the reference's link put on its own line)."""
    text = " ".join(tag.get_text(" ").split())
    links = " ".join(" ".join(a.get_text(" ").split()) for a in tag.find_all("a"))
    return bool(text) and (text == links or re.fullmatch(r"https?://\S+", text) is not None)


def lecturas_page_body(fragment_html: str) -> str:
    """
    The "Lecturas complementarias unidad N" page body from the unit's
    Material_de_referencia_UN.html (every activity's readings, in order):
    one "Lecturas complementarias" title (the document's own heading was shown
    again under it), without the template's "Básica:" / "Complementaria:"
    labels, as a bulleted list with each reference once — the unit's
    activities often list the same readings — and a link on its own line
    joined to the reference above it, so "(Disponible aquí)" follows the text.
    """
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(fragment_html, "html.parser")
    for p in soup.find_all('p'):
        text = p.get_text().strip().lower()
        # Handle possible encoding anomalies for Básica and Complementaria headers
        if any(text == t for t in ['básica:', 'bǭsica:', 'bsica:', 'bsica:', 'complementaria:', 'complementaria (opcional):']):
            p.decompose()
        elif text.rstrip(':').strip() in ('lecturas complementarias', 'material de referencia', 'lecturas de referencia'):
            p.decompose()

    # Each reference as HTML, in document order: a paragraph, or a list item.
    entries, others = [], []
    for tag in list(soup.contents):
        if not getattr(tag, "name", None):
            continue
        items = tag.find_all("li") if tag.name in ("ul", "ol") else [tag] if tag.name == "p" else None
        if items is None:
            others.append(str(tag))  # a table or anything else: kept as it was
            continue
        for item in items:
            if not item.get_text(strip=True) and not item.find("a"):
                continue
            inner = item.decode_contents().strip()
            if entries and _only_a_link(item):
                entries[-1] += " " + inner
            else:
                entries.append(_without_typed_marker(inner))

    seen, unique = set(), []
    for entry in entries:
        key = _reference_key(entry)
        if key and key not in seen:
            seen.add(key)
            unique.append(entry)
    body = ("<ul>" + "".join(f"<li>{e}</li>" for e in unique) + "</ul>") if unique else ""
    return "<p><strong>Lecturas complementarias</strong></p>" + body + "".join(others)


def add_pagina_materiales(driver, section_element, course_id, unidad_num, wait_time=10):
    wait = WebDriverWait(driver, wait_time)
    
    # Click 'Añadir una actividad o recurso'
    add_activity_btns = section_element.find_elements(By.CSS_SELECTOR, "button.activity-add, a.section-modchooser-link:not([data-action='addSection']), button.section-modchooser-link, [data-action='open-chooser']")
    if not add_activity_btns:
        logger.warning("Could not find 'Add activity' button.")
        return False
    add_activity_btn = add_activity_btns[-1]
    
    try:
        wait.until(EC.element_to_be_clickable(add_activity_btn)).click()
    except WebDriverException:
        driver.execute_script("arguments[0].click();", add_activity_btn)
        
    chooser = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".modchooser, .modal-dialog, .modal-content, [data-region='chooserdialogue']")))
    time.sleep(1)
    
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".modchooser .option, .modchooser .modchooser-item, .modal-dialog .option, .modal-dialog .modchooser-item, [data-region='chooserdialogue'] .option")))
    except TimeoutException:
        pass

    keywords = ["page", "página", "pagina"]
    options = chooser.find_elements(By.CSS_SELECTOR, ".option a, .option button, .option label, .modchooser-item, .option")
    
    found = False
    for option in options:
        text = option.text.lower()
        href = option.get_attribute("href") or ""
        data_name = option.get_attribute("data-name") or ""
        
        if any(k in text for k in keywords) or any(k in href for k in keywords) or any(k in data_name.lower() for k in keywords):
            if href and "javascript" not in href.lower():
                driver.get(href)
                found = True
                break
            else:
                try:
                    option.click()
                    found = True
                    break
                except WebDriverException:
                    driver.execute_script("arguments[0].click();", option)
                    found = True
                    break
                
    if not found:
        logger.warning("Could not find Page option in chooser.")
        return False
        
    try:
        wait.until(EC.presence_of_element_located((By.ID, "id_name")))
    except Exception:
        pass
        
    # Set Title
    name_input = wait.until(EC.presence_of_element_located((By.ID, "id_name")))
    driver.execute_script("arguments[0].value = '';", name_input)
    name_input.send_keys(f"Lecturas complementarias unidad {unidad_num}")
    driver.execute_script("arguments[0].dispatchEvent(new Event('change', {bubbles: true}));", name_input)

    # Build Content
    video_html = '<video class="nomediaplugin" crossorigin="anonymous" autoplay="autoplay" loop="loop" muted="true">   <source src="https://unisallevirtual.lasalle.edu.co/multimedia/etiquetas/Mat_Referencia.mp4">   RPLCMNT  </video>'
    
    html_file_path = os.path.join("workspace", str(course_id), "material", f"Material_de_referencia_U{unidad_num}.html")
    file_content = ""
    if os.path.exists(html_file_path):
        with open(html_file_path, "r", encoding="utf-8") as f:
            file_content = f.read()
            
        file_content = lecturas_page_body(file_content)
            
        file_content = format_urls_in_html(file_content, link_text="(Disponible aquí)")
        file_content = format_typography_in_html(file_content)
    else:
        logger.warning(f"File not found: {html_file_path}")
    
    full_content = video_html + file_content
    
    # Save output to a local file
    output_path = os.path.join("workspace", str(course_id), "material", f"Lecturas_complementarias_output_U{unidad_num}.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(full_content)
    logger.info(f"Saved Lecturas complementarias output to {output_path}")
    
    # Inject a space into Description (intro) without submitting, in case Moodle requires it
    inject_html_into_wysiwyg(driver, " ", wait_time, target_section="intro", submit_form=False)
    
    # Inject into Page content WYSIWYG without submitting
    success = inject_html_into_wysiwyg(driver, full_content, wait_time, target_section="contenido", submit_form=False)
    if not success: 
        logger.error("Failed to inject HTML into WYSIWYG")
        return False
        
    # Explicitly click "Save and return to course" (id_submitbutton2)
    try:
        submit_btn = wait.until(EC.element_to_be_clickable((By.ID, "id_submitbutton2")))
        try:
            submit_btn.click()
        except Exception:
            driver.execute_script("arguments[0].click();", submit_btn)
            
        try:
            wait.until(EC.staleness_of(submit_btn))
        except TimeoutException:
            # Check for validation errors if it didn't submit
            errors = driver.find_elements(By.CSS_SELECTOR, ".invalid-feedback, .error, .alert-danger")
            for err in errors:
                if err.is_displayed() and err.text:
                    logger.error(f"Validation error creating Page for Unidad {unidad_num}: {err.text}")
            time.sleep(1.5)
    except Exception as e:
        logger.error(f"Could not click save button for Page Unidad {unidad_num}: {e}")

    # Wait for redirect back to course view
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "body.path-course-view")))
    except Exception:
        pass

    progress.ok(f"Materiales de estudio agregados: Unidad {unidad_num}")
    return True

def materials_already_added(section_text: str, unidad_num: int) -> bool:
    """True if the unit's section already shows its "Lecturas complementarias unidad N" page."""
    pattern = rf"lecturas\s+complementarias\s+unidad\s+{unidad_num}(?!\d)"
    return re.search(pattern, " ".join((section_text or "").split()).lower()) is not None


def run_materiales_estudio_workflow(driver, course_id, wait_time=10, per_page_filter=False):
    """
    per_page_filter True: 'Complementos multimedia' could not be turned off for
    the whole course, so each 'Lecturas complementarias unidad N' page gets it
    off on its own (as the activities do), keeping its links plain.
    """
    logger.info(f"Starting Materiales de Estudio workflow for course {course_id}")
    
    # Ensure we are on the course homepage
    logger.info("Navigating to course homepage to find sections...")
    navigate_to_course(driver, Config.MOODLE_URL, course_id, wait_time)
    time.sleep(2)
    
    unidad_num = 1
    while True:
        logger.info(f"Processing Unidad {unidad_num}")
        
        # Navigate to course homepage at the start of each iteration to ensure all sections are visible
        navigate_to_course(driver, Config.MOODLE_URL, course_id, wait_time)
        time.sleep(2)
        
        try:
            sections = driver.find_elements(By.CSS_SELECTOR, "li.section")
            logger.info(f"Found {len(sections)} sections on the page.")
            target_section = None
            for sec in sections:
                try:
                    title_elem = sec.find_element(By.CSS_SELECTOR, ".sectionname, h3.sectionname, h4")
                    if f"UNIDAD {unidad_num}" in title_elem.text.upper():
                        target_section = sec
                        break
                except Exception:
                    if f"UNIDAD {unidad_num}" in sec.text.upper():
                        target_section = sec
                        break
                    
            if not target_section:
                if unidad_num == 1:
                    logger.warning("Could NOT find any section containing the text 'UNIDAD 1'. No study materials were added.")
                else:
                    logger.info(f"No hay sección 'UNIDAD {unidad_num}': materiales agregados a las {unidad_num - 1} unidades.")
                break
                
            if materials_already_added(target_section.text, unidad_num):
                # A repeated run (e.g. to redo only the quiz) added the label
                # and the page a second time.
                logger.info(f"Unidad {unidad_num}: ya tiene «Lecturas complementarias unidad {unidad_num}»; no se agregan de nuevo.")
                progress.info(f"Materiales de estudio ya presentes: Unidad {unidad_num}")
                unidad_num += 1
                continue

            logger.info(f"Successfully found section for Unidad {unidad_num}. Adding 'Área de texto y medios' (Etiqueta)...")
            add_etiqueta_materiales(driver, target_section, wait_time)
            time.sleep(2)
            
            # Find section again
            sections = driver.find_elements(By.CSS_SELECTOR, "li.section")
            for sec in sections:
                try:
                    title_elem = sec.find_element(By.CSS_SELECTOR, ".sectionname, h3.sectionname, h4")
                    if f"UNIDAD {unidad_num}" in title_elem.text.upper():
                        target_section = sec
                        break
                except Exception:
                    if f"UNIDAD {unidad_num}" in sec.text.upper():
                        target_section = sec
                        break
                        
            logger.info(f"Successfully added Etiqueta. Now adding 'Página' for Unidad {unidad_num}...")
            
            if getattr(Config, "ENABLE_LECTURAS_COMPLEMENTARIAS_UPLOAD", True):
                added = add_pagina_materiales(driver, target_section, course_id, unidad_num, wait_time)
                if added and per_page_filter:
                    disable_multimedia_filter_for_activity(driver, f"Lecturas complementarias unidad {unidad_num}", wait_time)
                time.sleep(2)
            else:
                logger.info("Skipping 'Página' (Lecturas complementarias) because ENABLE_LECTURAS_COMPLEMENTARIAS_UPLOAD is False.")
            
        except Exception as e:
            logger.error(f"Error processing Unidad {unidad_num}: {e}")
            break
            
        unidad_num += 1
            
    logger.info("Finished Materiales de Estudio workflow")
