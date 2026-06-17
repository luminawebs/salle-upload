import time
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

logger = logging.getLogger(__name__)

def inject_html_into_wysiwyg(driver, html_content: str, wait_time: int = 10, target_section: str = "descripcion") -> bool:
    """
    Injects HTML into the Moodle WYSIWYG editor (handles both TinyMCE and Atto).
    Specifically prioritized to handle sandbox_wysiwyg.html.
    target_section: "descripcion" (introeditor) or "contenido" (page)
    """
    wait = WebDriverWait(driver, wait_time)
    try:
        # 1. Identify textarea
        textarea = None
        target_names = ["introeditor[text]", "page[text]", "summary_editor[text]"]
        if target_section == "contenido":
            target_names = ["page[text]", "introeditor[text]", "summary_editor[text]"]
        elif target_section == "resumen":
            target_names = ["summary_editor[text]", "introeditor[text]", "page[text]"]
            
        for name in target_names:
            elements = driver.find_elements(By.CSS_SELECTOR, f"textarea[name='{name}']")
            if elements:
                textarea = elements[0]
                break

        if not textarea:
            textareas = driver.find_elements(By.TAG_NAME, "textarea")
            for ta in textareas:
                if "editor" in ta.get_attribute("id") or "editor" in ta.get_attribute("class"):
                    textarea = ta
                    break
            if not textarea and textareas:
                textarea = textareas[0]
        
        # 2. Inject into raw textarea
        if textarea:
            driver.execute_script("arguments[0].value = arguments[1];", textarea, html_content)

        # 3. Inject into TinyMCE if present (Sandbox uses this)
        textarea_id = textarea.get_attribute("id") if textarea else ""
        driver.execute_script(
            f"""
            if (typeof tinymce !== 'undefined') {{
                var editorId = arguments[1];
                var editor = tinymce.get(editorId);
                if (editor) {{
                    editor.setContent(arguments[0]);
                }} else {{
                    // Fallback to first editor if specific one is not found
                    if (tinymce.editors.length > 0) {{
                        tinymce.editors[0].setContent(arguments[0]);
                    }}
                }}
            }}
            """,
            html_content,
            textarea_id
        )

        # 4. Inject into Atto if present (Older Moodle)
        try:
            atto = driver.find_elements(By.CSS_SELECTOR, ".editor_atto_content")
            if atto:
                driver.execute_script(
                    "arguments[0].innerHTML = arguments[1];", atto[0], html_content
                )
        except Exception:
            pass

        time.sleep(0.5)

        # 5. Submit form
        submit_btn = wait.until(
            EC.element_to_be_clickable(
                (
                    By.CSS_SELECTOR,
                    "input[type='submit'][name='submitbutton'], "
                    "button[type='submit'][name='submitbutton'], "
                    "input[type='submit'][value='Save and return to course'], "
                    "input[type='submit'][id='id_submitbutton'], "
                    "input[type='submit'][id='id_submitbutton2'], "
                    "button[id='id_submitbutton'], "
                    "button[id='id_submitbutton2']",
                )
            )
        )
        submit_btn.click()

        try:
            wait.until(EC.staleness_of(submit_btn))
        except TimeoutException:
            time.sleep(1.5)

        return True

    except Exception as e:
        logger.error(f"Error injecting HTML into WYSIWYG: {e}")
        return False

def extract_html_from_wysiwyg(driver, target_section: str = "descripcion") -> str:
    """
    Extracts HTML from the Moodle WYSIWYG editor (handles both TinyMCE and Atto).
    target_section: "descripcion" (introeditor) or "contenido" (page)
    """
    try:
        # 1. Identify textarea
        textarea = None
        target_names = ["introeditor[text]", "page[text]", "summary_editor[text]"]
        if target_section == "contenido":
            target_names = ["page[text]", "introeditor[text]", "summary_editor[text]"]
        elif target_section == "resumen":
            target_names = ["summary_editor[text]", "introeditor[text]", "page[text]"]
            
        for name in target_names:
            elements = driver.find_elements(By.CSS_SELECTOR, f"textarea[name='{name}']")
            if elements:
                textarea = elements[0]
                break

        if not textarea:
            textareas = driver.find_elements(By.TAG_NAME, "textarea")
            for ta in textareas:
                if "editor" in ta.get_attribute("id") or "editor" in ta.get_attribute("class"):
                    textarea = ta
                    break
            if not textarea and textareas:
                textarea = textareas[0]
                
        textarea_id = textarea.get_attribute("id") if textarea else ""

        # 2. Try TinyMCE first
        content = driver.execute_script(
            f"""
            if (typeof tinymce !== 'undefined') {{
                var editorId = arguments[0];
                var editor = tinymce.get(editorId);
                if (editor) {{
                    return editor.getContent();
                }} else if (tinymce.editors.length > 0) {{
                    return tinymce.editors[0].getContent();
                }}
            }}
            return null;
            """,
            textarea_id
        )

        if content is not None:
            return content

        # 3. Try Atto
        try:
            atto = driver.find_elements(By.CSS_SELECTOR, ".editor_atto_content")
            if atto:
                return atto[0].get_attribute("innerHTML")
        except Exception:
            pass

        # 4. Fallback to raw textarea
        if textarea:
            return textarea.get_attribute("value")
            
        return ""
    except Exception as e:
        logger.error(f"Error extracting HTML from WYSIWYG: {e}")
        return ""
