import os
import logging
import re
from selenium.webdriver.support.ui import WebDriverWait
from actions.docx_upload_actions import get_edit_url_for_activity
from core.wysiwyg_handler import inject_html_into_wysiwyg
from actions.html_transformer import generate_dynamic_generalidades_html, get_image_base64

logger = logging.getLogger(__name__)

def run_generalidades_accordion_upload_workflow(driver, course_id, wait_time=10):
    logger.info("Executing Generalidades Accordion Upload workflow...")
    
    # 1. Find the "Introducción General" label and edit it
    success = get_edit_url_for_activity(driver, "Introducción General", wait_time)
    if not success:
        logger.error("Could not find 'Introducción General' activity to upload accordion.")
        return False
        
    # 2. Get the template and raw_docx to generate the accordion HTML
    template_path = os.path.join("workspace", "example_course", "GENERALIDADES DEL CURSO.html")
    course_dir = os.path.join("workspace", str(course_id)) if course_id else "workspace"
    extracted_path = os.path.join(course_dir, "raw_docx_extracted.html")
    
    if not os.path.exists(template_path):
        logger.error(f"Accordion template path does not exist: {template_path}. Skipping accordion upload.")
        # We should cancel the edit form
        try:
            from selenium.webdriver.common.by import By
            cancel_btn = driver.find_element(By.CSS_SELECTOR, "input[name='cancel'], button[name='cancel'], #id_cancel")
            driver.execute_script("arguments[0].click();", cancel_btn)
        except:
            pass
        return False
        
    if os.path.exists(extracted_path):
        try:
            html_markers = generate_dynamic_generalidades_html(extracted_path, template_path)
        except Exception as e:
            logger.error(f"Error generating dynamic generalidades: {e}")
            with open(template_path, "r", encoding="utf-8") as f:
                html_markers = f.read()
    else:
        with open(template_path, "r", encoding="utf-8") as f:
            html_markers = f.read()
            
    # 3. Replace the images
    def replace_draft_image_tag(match):
        full_tag = match.group(0)
        src_match = re.search(r'src=["\']([^"\']*)["\']', full_tag)
        if not src_match:
            return full_tag
            
        full_url = src_match.group(1)
        filename = full_url.split('/')[-1].split('?')[0].split('#')[0]
        
        if filename.lower() in ["profesor.jpg", "docente.jpg"] and course_id:
            raw_doc_path = os.path.join("workspace", str(course_id), "raw_docx_extracted.html")
            if os.path.exists(raw_doc_path):
                from bs4 import BeautifulSoup
                with open(raw_doc_path, "r", encoding="utf-8") as rf:
                    raw_soup = BeautifulSoup(rf.read(), "html.parser")
                    for td in raw_soup.find_all("td"):
                        if "Foto del perfil" in td.get_text():
                            next_td = td.find_next_sibling("td")
                            if next_td:
                                img = next_td.find("img")
                                if img and img.has_attr("src"):
                                    docx_img_src = img["src"]
                                    docx_img_path = os.path.join("workspace", str(course_id), docx_img_src)
                                    if os.path.exists(docx_img_path):
                                        import base64
                                        with open(docx_img_path, "rb") as img_file:
                                            encoded_string = base64.b64encode(img_file.read()).decode('utf-8')
                                        ext = os.path.splitext(docx_img_path)[1].lower().replace('.', '')
                                        mime_type = f"image/{ext}" if ext in ['png', 'jpg', 'jpeg', 'gif'] else "image/png"
                                        new_src = f"data:{mime_type};base64,{encoded_string}"
                                        return full_tag.replace(full_url, new_src)
                                        
        base64_data = get_image_base64(filename)
        if base64_data:
            return full_tag.replace(full_url, base64_data)
        
        logger.warning(f"Imagen del Docente no encontrada ({filename}). No se agregará imagen en Generalidades.")
        return ""

    html_markers = re.sub(
        r'<img[^>]*src=["\'][^"\']*draftfile\.php[^"\']*["\'][^>]*>', 
        replace_draft_image_tag, 
        html_markers,
        flags=re.IGNORECASE
    )
    
    # 4. Inject the accordion HTML completely overriding the existing wysiwyg content
    # Note: target_section for Labels is 'intro' because the whole label is just an introeditor.
    success = inject_html_into_wysiwyg(driver, html_markers, wait_time, target_section="intro", submit_form=True)
    if success:
        logger.info("Successfully uploaded Generalidades Accordion.")
        
    return success
