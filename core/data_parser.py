import os
import logging
import mammoth
import re
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

def parse_docx_to_html(docx_path: str, course_id: int) -> str:
    """
    Parses a docx file using mammoth and returns the raw HTML string.
    Images are extracted and saved to assets/<course_id>/imgs/
    """
    if not os.path.exists(docx_path):
        logger.warning(f"DOCX file not found: {docx_path}")
        return ""

    import hashlib

    img_dir = os.path.join("assets", str(course_id), "imgs")
    os.makedirs(img_dir, exist_ok=True)

    def convert_image(image):
        with image.open() as image_bytes_io:
            image_bytes = image_bytes_io.read()
        
        # Determine extension from content_type
        content_type = image.content_type
        ext = "png"
        if content_type == "image/jpeg":
            ext = "jpg"
        elif content_type == "image/gif":
            ext = "gif"
            
        # Create a unique filename based on hash
        hash_str = hashlib.md5(image_bytes).hexdigest()[:10]
        filename = f"img_{hash_str}.{ext}"
        filepath = os.path.join(img_dir, filename)
        
        with open(filepath, "wb") as f:
            f.write(image_bytes)
            
        # Return the src to be embedded in the HTML
        return {"src": f"imgs/{filename}"}

    try:
        with open(docx_path, "rb") as docx_file:
            result = mammoth.convert_to_html(
                docx_file,
                convert_image=mammoth.images.img_element(convert_image)
            )
            html = result.value # The generated HTML
            messages = result.messages # Any messages, such as warnings during conversion
            if messages:
                logger.debug(f"Mammoth messages for {docx_path}: {messages}")
            return html
    except Exception as e:
        logger.error(f"Error parsing {docx_path}: {e}")
        return ""

def extract_section_html(full_html: str, section_title: str) -> str:
    """
    Given a full HTML string from docx parsing, extracts the content under a specific heading.
    This is a basic placeholder that will need refinement based on exact docx structure.
    """
    if not full_html:
        return ""
        
    soup = BeautifulSoup(full_html, "html.parser")
    # Finding a heading that matches the section_title
    for heading in soup.find_all(['h1', 'h2', 'h3', 'h4']):
        if section_title.lower() in heading.get_text().lower():
            # Gather all siblings until the next heading of same or higher level
            content = []
            sibling = heading.find_next_sibling()
            while sibling and sibling.name not in ['h1', 'h2', 'h3', 'h4']:
                content.append(str(sibling))
                sibling = sibling.find_next_sibling()
            return "".join(content)
            
    return ""

def run_docx_parsing_workflow(course_id: int):
    """
    Finds the docx for the given course_id and dumps the extracted HTML
    to assets/<course_id>/raw_docx_extracted.html so the user can validate it.
    """
    logger.info(f"Executing DOCX parsing workflow for course {course_id}...")
    base_dir = os.path.join("assets", str(course_id))
    # Assuming docx is named as course_id.docx
    docx_path = os.path.join(base_dir, f"{course_id}.docx")
    output_path = os.path.join(base_dir, "raw_docx_extracted.html")

    html_content = parse_docx_to_html(docx_path, course_id)
    if html_content:
        os.makedirs(base_dir, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        logger.info(f"  ✓ DOCX successfully extracted and saved to {output_path}")
    else:
        logger.warning(f"  Failed to extract DOCX or file not found at {docx_path}")

def run_docx_splitting_workflow(course_id: int):
    """
    Reads assets/<course_id>/raw_docx_extracted.html and splits it into the necessary
    HTML fragments (actividades, material de referencia, etc.).
    """
    logger.info(f"Executing DOCX splitting workflow for course {course_id}...")
    base_dir = os.path.join("assets", str(course_id))
    raw_html_path = os.path.join(base_dir, "raw_docx_extracted.html")

    if not os.path.exists(raw_html_path):
        logger.warning(f"  raw_docx_extracted.html not found for course {course_id}. Run DOCX parsing first.")
        return

    with open(raw_html_path, "r", encoding="utf-8") as f:
        full_html = f.read()

    soup = BeautifulSoup(full_html, "html.parser")
    
    # Trackers
    current_unit = 0
    current_activity = 0
    
    # Output directories
    output_dirs = {
        "actividades": os.path.join(base_dir, "actividades"),
        "material": os.path.join(base_dir, "material"),
        "introduccion": os.path.join(base_dir, "introduccion"),
    }
    for d in output_dirs.values():
        os.makedirs(d, exist_ok=True)
        
    # Helpers
    def extract_until_next_header(start_tag, stop_texts=None, stop_tags=None):
        content = []
        curr = start_tag.find_next_sibling()
        while curr:
            if stop_tags and curr.name in stop_tags:
                break
            text = curr.get_text().strip().upper()
            if stop_texts and any(stop in text for stop in stop_texts):
                break
            content.append(str(curr))
            curr = curr.find_next_sibling()
        return "".join(content)

    # 1. Extract Introducción General
    for h1 in soup.find_all('h1'):
        if "PRESENTACIÓN DEL ESPACIO ACADÉMICO" in h1.get_text().upper():
            intro_html = extract_until_next_header(h1, stop_texts=["PLAN DE FORMACIÓN"])
            if intro_html:
                with open(os.path.join(output_dirs["introduccion"], "introduccion_general.html"), "w", encoding="utf-8") as f:
                    f.write(intro_html)
                logger.info("  ✓ Extracted introduccion_general.html")
            break

    # 2. Extract Activities and Material de Referencia
    trs = soup.find_all('tr')
    i = 0
    while i < len(trs):
        tr = trs[i]
        text = tr.get_text().strip().upper()
        
        # Detect Unit
        if "UNIDAD DIDÁCTICA" in text:
            m = re.search(r'UNIDAD DIDÁCTICA (\d+)', text)
            if m:
                current_unit = int(m.group(1))

        # Detect Activity
        if re.search(r'ACTIVIDAD\s+\d+\s*:', text):
            m = re.search(r'ACTIVIDAD\s+(\d+)\s*:', text)
            if m:
                current_activity = int(m.group(1))
                act_html_parts = []
                # Include the current row's td contents
                for td in tr.find_all('td'):
                    act_html_parts.append(td.decode_contents())
                
                # Look ahead for following rows belonging to this activity
                i += 1
                while i < len(trs):
                    next_tr = trs[i]
                    next_text = next_tr.get_text().strip().upper()
                    if re.search(r'ACTIVIDAD\s+\d+\s*:', next_text) or "UNIDAD DIDÁCTICA" in next_text or "INFORMACIÓN PARA EL EQUIPO" in next_text:
                        # Reached the end of this activity, step back one so the outer loop processes it
                        i -= 1
                        break
                    for td in next_tr.find_all('td'):
                        act_html_parts.append(td.decode_contents())
                    i += 1
                
                act_html = "".join(act_html_parts)
                with open(os.path.join(output_dirs["actividades"], f"actividad{current_activity}.html"), "w", encoding="utf-8") as f:
                    f.write(act_html)
                logger.info(f"  ✓ Extracted actividad{current_activity}.html")

        # Detect Material de Referencia (Lecturas complementarias)
        elif "LECTURAS COMPLEMENTARIAS" in text or "MATERIAL DE REFERENCIA" in text:
            mat_html_parts = []
            for td in tr.find_all('td'):
                mat_html_parts.append(td.decode_contents())
                
            i += 1
            while i < len(trs):
                next_tr = trs[i]
                next_text = next_tr.get_text().strip().upper()
                if re.search(r'ACTIVIDAD\s+\d+\s*:', next_text) or "UNIDAD DIDÁCTICA" in next_text or "INFORMACIÓN PARA EL EQUIPO" in next_text:
                    i -= 1
                    break
                for td in next_tr.find_all('td'):
                    mat_html_parts.append(td.decode_contents())
                i += 1
                
            mat_html = "".join(mat_html_parts)
            unit_num = current_unit if current_unit > 0 else 1
            mat_file = os.path.join(output_dirs["material"], f"Material_de_referencia_U{unit_num}.html")
            mode = "a" if os.path.exists(mat_file) else "w"
            with open(mat_file, mode, encoding="utf-8") as f:
                f.write(mat_html)
            logger.info(f"  ✓ Appended to Material_de_referencia_U{unit_num}.html")
        
        i += 1

    logger.info("  ✓ DOCX splitting workflow completed.")
