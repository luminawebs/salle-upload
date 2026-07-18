import copy
import json
import logging
import os
import re
import sys
import time

from bs4 import BeautifulSoup, Comment
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from html_generator.generate_html import clean_html, wrap_bibliographic_title_in_bold

from actions.moodle_actions import navigate_to_course
from config.settings import Config

logger = logging.getLogger(__name__)

ACTUALIDAD_SOURCE_NAME = "VIR - RECURSOS DE ACTUALIDAD"
ACTUALIDAD_TARGET_TEMPLATE = "S{week} | Actualidad"
ACTUALIDAD_INTRO_SNIPPET = "En esta sección se presentan recursos digitales actuales"

RECURSO_PREFIX_RE = re.compile(r"(?i)(recurso|r)\s*\d+\s*:?\s*")
URL_RE = re.compile(r"https?://[^\s<>\")]+")


def sanitize_actualidad_output(html_str):
    """
    Strips Moodle labels like 'Recurso 1:' / 'Recurso 2:' and raw http(s) URLs from HTML.
    Used so JSON and generated actualidad files match the desired final output.
    """
    if not html_str or not str(html_str).strip():
        return html_str if html_str is not None else ""

    soup = BeautifulSoup(html_str, "html.parser")

    for anchor in soup.find_all("a"):
        href = (anchor.get("href") or "").strip()
        text = anchor.get_text(strip=True)
        if not text:
            # If both text and href are empty, decompose it
            if not href:
                anchor.decompose()
            continue
            
        text_lower = text.lower()
        href_lower = href.lower() if href else ""
        
        # If the text is just the raw URL, hide the text to keep the UI clean,
        # but keep the <a> tag so its href can be saved to json for glossary links.
        if href_lower.startswith(("http://", "https://")):
            if text_lower == href_lower or text_lower in href_lower or href_lower in text_lower or text_lower.startswith("http"):
                anchor.string = ""
                continue

    for text_node in soup.find_all(string=True):
        if isinstance(text_node, Comment):
            continue
        parent = text_node.parent
        if parent is not None and parent.name in ("script", "style"):
            continue
        raw = str(text_node)
        cleaned = RECURSO_PREFIX_RE.sub("", raw)
        cleaned = URL_RE.sub("", cleaned)
        if cleaned != raw:
            text_node.replace_with(cleaned)

    for tag in soup.find_all(["p", "li"]):
        if not tag.get_text(strip=True) and not tag.find("img"):
            tag.decompose()

    return str(soup)


def clean_actualidad_html(raw_html):
    """
    Cleans raw Moodle HTML while preserving meaningful links and text blocks.
    """
    if not raw_html:
        return ""

    soup = BeautifulSoup(raw_html, "html.parser")

    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    for tag in soup.find_all(["script", "style"]):
        tag.decompose()

    for tag in soup.find_all(True):
        if tag.name in ["span", "font", "div", "h1", "h2", "h3", "h4", "h5", "h6"]:
            tag.unwrap()
            continue

        attrs = dict(tag.attrs)
        tag.attrs = {}
        if tag.name == "a" and "href" in attrs:
            tag["href"] = attrs["href"]
        if tag.name == "img" and "src" in attrs:
            tag["src"] = attrs["src"]
            if "alt" in attrs:
                tag["alt"] = attrs["alt"]

    for tag in soup.find_all(True):
        if tag.name in ["p", "li", "a", "strong", "em", "b", "i"] and not tag.get_text(
            " ", strip=True
        ):
            tag.decompose()

    return str(soup)


def extract_actualidad_items(clean_html_str):
    """
    Converts cleaned HTML into a list of resource blocks for the actualidad template.
    """
    if not clean_html_str:
        return []

    soup = BeautifulSoup(clean_html_str, "html.parser")
    items = []

    for tag in soup.find_all(["p", "li"]):
        if tag.find_parent(["p", "li"]):
            continue

        text = tag.get_text(" ", strip=True)
        if not text or not re.search(r'[a-zA-Z0-9]', text):
            continue

        normalized_text = " ".join(text.split())
        if normalized_text.lower() == "recursos de actualidad":
            continue
        if ACTUALIDAD_INTRO_SNIPPET.lower() in normalized_text.lower():
            continue

        item_html = "".join(str(child) for child in tag.contents).strip()
        if not item_html:
            item_html = normalized_text

        items.append(item_html)

    if items:
        return items

    fallback_text = " ".join(soup.get_text(" ", strip=True).split())
    if fallback_text:
        return [fallback_text]

    return []



def process_actualidad_html(raw_html):
    """
    Returns the cleaned HTML plus parsed resource items for local persistence.
    """
    cleaned_html = clean_actualidad_html(raw_html)
    cleaned_html = sanitize_actualidad_output(cleaned_html)
    cleaned_html = clean_html(cleaned_html)
    cleaned_html = wrap_bibliographic_title_in_bold(cleaned_html)
    return {
        "html_content": cleaned_html,
        "items": extract_actualidad_items(cleaned_html),
    }


def _append_fragment(target_tag, fragment_html):
    fragment_soup = BeautifulSoup(fragment_html, "html.parser")
    nodes = list(fragment_soup.contents)
    if not nodes:
        paragraph = fragment_soup.new_tag("p")
        paragraph.string = fragment_html
        target_tag.append(paragraph)
        return

    has_block = any(getattr(node, "name", None) in ["p", "ul", "ol"] for node in nodes)
    if has_block:
        for node in nodes:
            target_tag.append(copy.deepcopy(node))
        return

    paragraph = fragment_soup.new_tag("p")
    for node in nodes:
        paragraph.append(copy.deepcopy(node))
    target_tag.append(paragraph)


def generate_actualidad_html_file(parsed_data, template_path, output_path):
    """
    Populates the actualidad template with extracted resource cards.
    """
    with open(template_path, "r", encoding="utf-8") as template_file:
        template_html = template_file.read()

    soup = BeautifulSoup(template_html, "html.parser")
    grid = soup.find("div", class_="grid-virtual-x2")
    if not grid:
        raise ValueError("Actualidad template is missing '.grid-virtual-x2'.")

    prototype_card = grid.find("div", class_="virtual-card-2")
    if not prototype_card:
        raise ValueError("Actualidad template is missing a '.virtual-card-2' prototype.")
    prototype_card = copy.deepcopy(prototype_card)

    for existing_card in grid.find_all("div", class_="virtual-card-2"):
        existing_card.decompose()

    items = parsed_data.get("items", [])
    if not items and parsed_data.get("html_content"):
        items = [parsed_data["html_content"]]

    for item_html in items:
        card = copy.deepcopy(prototype_card)
        card_body = card.find("div", class_="vs-card-2-2")
        if not card_body:
            continue

        card_body.clear()
        _append_fragment(card_body, item_html)
        grid.append(card)

    # Remove all <a> tags from the final generated HTML
    for a in soup.find_all("a"):
        a.unwrap()

    final_html = soup.prettify(formatter="minimal")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as output_file:
        output_file.write(final_html)


def extract_actualidad_content(driver, week_name, wait_time=10):
    """
    Opens only `VIR - RECURSOS DE ACTUALIDAD` in the target week and extracts page HTML.
    """
    wait = WebDriverWait(driver, wait_time)
    logger.info(f"Extracting '{ACTUALIDAD_SOURCE_NAME}' from '{week_name}'")

    try:
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
        section_li = title_element.find_element(
            By.XPATH, "./ancestor::li[contains(@class, 'section')]"
        )

        activity_xpath = (
            ".//li[contains(@class, 'activity')]//*[contains(@class, 'instancename') "
            f"and contains(text(), '{ACTUALIDAD_SOURCE_NAME}')]"
        )
        try:
            activity_title = section_li.find_element(By.XPATH, activity_xpath)
        except Exception:
            logger.warning(f"Resource '{ACTUALIDAD_SOURCE_NAME}' not found in '{week_name}'.")
            return None

        activity_li = activity_title.find_element(
            By.XPATH, "./ancestor::li[contains(@class, 'activity')]"
        )

        dropdown_toggle = activity_li.find_element(
            By.CSS_SELECTOR, "a.dropdown-toggle[title='Editar'], a[aria-label='Editar']"
        )
        try:
            wait.until(EC.element_to_be_clickable(dropdown_toggle)).click()
        except WebDriverException:
            driver.execute_script("arguments[0].click();", dropdown_toggle)

        edit_option_xpath = (
            ".//a[contains(@class, 'dropdown-item') and "
            "(contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'editar ajustes') "
            "or contains(@href, 'modedit.php'))]"
        )
        edit_option = wait.until(lambda d: activity_li.find_element(By.XPATH, edit_option_xpath))
        edit_href = edit_option.get_attribute("href")
        
        original_window = driver.current_window_handle
        use_new_tab = Config.ENABLE_ACTUALIDAD_EXPORT and edit_href
        
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

        logger.info("Waiting for actualidad settings page to load...")
        time.sleep(1)

        textarea_css = "textarea[name='page[text]']"
        try:
            textarea = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, textarea_css)))
            raw_html = driver.execute_script("return arguments[0].value;", textarea)
            if not raw_html or not raw_html.strip():
                try:
                    atto_editor = driver.find_element(
                        By.CSS_SELECTOR, "#fitem_id_page .editor_atto_content"
                    )
                    raw_html = driver.execute_script("return arguments[0].innerHTML;", atto_editor)
                except Exception:
                    raw_html = None
        except TimeoutException:
            logger.error(f"Could not find page content editor for '{week_name}'.")
            if use_new_tab:
                driver.close()
                driver.switch_to.window(original_window)
            else:
                driver.back()
            return None

        if use_new_tab:
            driver.close()
            driver.switch_to.window(original_window)
        else:
            driver.back()
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "body.path-course-view")))
        return raw_html

    except Exception as exc:
        logger.error(f"Failed to extract actualidad from '{week_name}': {exc}")
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


def upload_actualidad_content(driver, course_id, week_name, resource_name, html_content, wait_time=10):
    """
    Uploads generated actualidad HTML into the exact `S{week} | Actualidad` page resource.
    """
    wait = WebDriverWait(driver, wait_time)
    logger.info(f"Uploading content to '{resource_name}' in '{week_name}'")

    try:
        if "course/view.php" not in driver.current_url:
            navigate_to_course(driver, Config.MOODLE_URL, course_id, wait_time)

        try:
            try:
                alert = driver.switch_to.alert
                logger.warning(f"Unexpected alert found: {alert.text}. Dismissing.")
                alert.dismiss()
            except Exception:
                pass

            quick_wait = WebDriverWait(driver, 5)
            section_xpath = (
                f"//li[contains(@class, 'section')][descendant::*[contains(@class, 'sectionname') "
                f"or self::h3 or self::h4][contains(., '{week_name}')]]"
            )
            section_li = quick_wait.until(
                EC.presence_of_element_located((By.XPATH, section_xpath))
            )
        except TimeoutException:
            logger.warning(f"Section '{week_name}' not found. Verify if sections were renamed correctly.")
            return False

        activity_xpath = (
            ".//li[contains(@class, 'activity')]//*[contains(@class, 'instancename') "
            f"and contains(text(), '{resource_name}')]"
        )
        try:
            activity_title = section_li.find_element(By.XPATH, activity_xpath)
        except Exception:
            logger.warning(f"Resource '{resource_name}' not found in '{week_name}'.")
            return False

        activity_li = activity_title.find_element(
            By.XPATH, "./ancestor::li[contains(@class, 'activity')]"
        )

        dropdown_toggle = activity_li.find_element(
            By.CSS_SELECTOR, "a.dropdown-toggle[title='Editar'], a[aria-label='Editar']"
        )
        try:
            wait.until(EC.element_to_be_clickable(dropdown_toggle)).click()
        except Exception:
            driver.execute_script("arguments[0].click();", dropdown_toggle)

        edit_option_xpath = (
            ".//a[contains(@class, 'dropdown-item') and "
            "(contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'editar ajustes') "
            "or contains(@href, 'modedit.php'))]"
        )
        edit_option = wait.until(lambda d: activity_li.find_element(By.XPATH, edit_option_xpath))
        edit_href = edit_option.get_attribute("href")
        
        original_window = driver.current_window_handle
        use_new_tab = Config.ENABLE_ACTUALIDAD_EXPORT and edit_href
        
        if use_new_tab:
            driver.execute_script("window.open(arguments[0], '_blank');", edit_href)
            for window_handle in driver.window_handles:
                if window_handle != original_window:
                    driver.switch_to.window(window_handle)
                    break
        else:
            try:
                wait.until(EC.element_to_be_clickable(edit_option)).click()
            except Exception:
                driver.execute_script("arguments[0].click();", edit_option)

        logger.info("Waiting for actualidad settings page to load...")
        submit_btn_css = "#id_submitbutton, input[name='submitbutton'], button[name='submitbutton']"
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, submit_btn_css)))

        textarea_css = "textarea[name='page[text]']"
        try:
            textarea = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, textarea_css)))
            driver.execute_script("arguments[0].value = arguments[1];", textarea, html_content)

            try:
                atto_editor = driver.find_element(By.CSS_SELECTOR, ".editor_atto_content")
                driver.execute_script("arguments[0].innerHTML = arguments[1];", atto_editor, html_content)
            except Exception:
                logger.info("Atto editor not found, updated textarea directly.")

            driver.execute_script(
                "var textarea = document.querySelector(arguments[0]);"
                "if (!textarea) { return; }"
                "textarea.dispatchEvent(new Event('change', { bubbles: true }));"
                "textarea.dispatchEvent(new Event('input', { bubbles: true }));",
                textarea_css,
            )
            time.sleep(2)
        except Exception as exc:
            logger.error(f"Failed to set actualidad editor content: {exc}")
            if use_new_tab:
                driver.close()
                driver.switch_to.window(original_window)
            return False

        logger.info("Saving changes...")
        try:
            submit_btn = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, submit_btn_css))
            )
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", submit_btn)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", submit_btn)
        except Exception as exc:
            logger.error(f"Could not find or click save button: {exc}")
            if use_new_tab:
                driver.close()
                driver.switch_to.window(original_window)
            return False

        try:
            save_wait = WebDriverWait(driver, 40)
            save_wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "body.path-course-view, #region-main"))
            )
            logger.info(f"Successfully uploaded content to '{week_name}'.")
            if use_new_tab:
                driver.close()
                driver.switch_to.window(original_window)
            return True
        except TimeoutException:
            if "course/view.php" in driver.current_url:
                logger.info(f"Redirection detected via URL for '{week_name}'.")
                if use_new_tab:
                    driver.close()
                    driver.switch_to.window(original_window)
                return True
            logger.error(f"Timeout waiting for redirection after saving '{week_name}'.")
            if use_new_tab:
                driver.close()
                driver.switch_to.window(original_window)
            return False

    except Exception as exc:
        logger.error(f"Error during actualidad upload to '{week_name}': {exc}")
        try:
            if "original_window" in locals() and "use_new_tab" in locals() and use_new_tab:
                if driver.current_window_handle != original_window:
                    driver.close()
                    driver.switch_to.window(original_window)
        except Exception:
            pass
        return False


def run_actualidad_export_workflow(driver, course_id, wait_time=10):
    """
    Extracts, cleans, stores, generates, and uploads actualidad content week by week.
    """
    logger.info(f"Starting Actualidad export workflow for course {course_id}...")

    json_path = os.path.join("assets", str(course_id), "contenidos.json")
    if not os.path.exists(json_path):
        logger.warning(f"Mapping file {json_path} not found. Skipping actualidad export.")
        return False

    with open(json_path, "r", encoding="utf-8") as json_file:
        try:
            contenidos_data = json.load(json_file)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON in {json_path}")
            return False

    template_path = os.path.join("assets", "templates", "actualidad.html")
    if not os.path.exists(template_path):
        logger.error(f"Actualidad template not found at {template_path}. Cannot generate HTML files.")
        return False

    updated = False
    for week_number in range(1, 9):
        week_name = f"Semana {week_number}"
        if week_name not in contenidos_data:
            logger.info(f"{week_name} not found in json data, skipping.")
            continue

        raw_html = extract_actualidad_content(driver, week_name, wait_time)
        if raw_html is None:
            continue

        processed_data = process_actualidad_html(raw_html)
        contenidos_data[week_name]["actualidad"] = processed_data
        updated = True
        logger.info(f"Successfully processed actualidad for {week_name}")

        output_filename = f"s{week_number}_actualidad.html"
        output_path = os.path.join("assets", str(course_id), "actualidad", output_filename)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        generate_actualidad_html_file(processed_data, template_path, output_path)
        logger.info(f"Generated Actualidad HTML at {output_path}")
        time.sleep(1)

    if not updated:
        logger.info("No actualidad content was extracted or updated.")
        return True

    with open(json_path, "w", encoding="utf-8") as json_file:
        json.dump(contenidos_data, json_file, ensure_ascii=False, indent=4)
    logger.info(f"Successfully updated {json_path} with actualidad content.")

    logger.info("Starting upload of generated Actualidad HTML files to Moodle...")
    for week_number in range(1, 9):
        output_filename = f"s{week_number}_actualidad.html"
        output_path = os.path.join("assets", str(course_id), "actualidad", output_filename)
        if not os.path.exists(output_path):
            logger.debug(f"File {output_path} not found, skipping upload for {week_number}.")
            continue

        with open(output_path, "r", encoding="utf-8") as html_file:
            html_to_upload = html_file.read()

        week_name = f"Semana {week_number}"
        resource_name = ACTUALIDAD_TARGET_TEMPLATE.format(week=week_number)
        success = upload_actualidad_content(
            driver, course_id, week_name, resource_name, html_to_upload, wait_time
        )
        if success:
            logger.info(f"Successfully uploaded {output_filename} to {week_name}")
        else:
            logger.error(f"Failed to upload {output_filename} to {week_name}")

    return True
