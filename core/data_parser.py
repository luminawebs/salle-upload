import os
import logging
import mammoth
import re
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from xml.dom import minidom

logger = logging.getLogger(__name__)

def parse_docx_to_html(docx_path: str, course_id: int) -> str:
    """
    Parses a docx file using mammoth and returns the raw HTML string.
    Images are extracted and saved to workspace/<course_id>/imgs/
    """
    if not os.path.exists(docx_path):
        logger.warning(f"DOCX file not found: {docx_path}")
        return ""

    import hashlib

    img_dir = os.path.join("workspace", str(course_id), "imgs")
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
    base_dir = os.path.join("workspace", str(course_id))
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
    Reads workspace/<course_id>/raw_docx_extracted.html and splits it into the necessary
    HTML fragments (actividades, material de referencia, etc.).
    """
    logger.info(f"Executing DOCX splitting workflow for course {course_id}...")
    base_dir = os.path.join("workspace", str(course_id))
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
        "glosario": os.path.join(base_dir, "glosario"),
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

    # 1.5 Extract Glosario
    glosario_found = False
    for p in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'td']):
        if "GLOSARIO" in p.get_text().upper().strip():
            # The glosario is typically in the following elements. We can try to look for the table next to it.
            # Or if it's already inside a table, we can extract the rows.
            table = p.find_next('table')
            if not table and p.find_parent('table'):
                table = p.find_parent('table')
                
            if table and not glosario_found:
                glosario_found = True
                glosario_root = ET.Element("GLOSARIO")
                info = ET.SubElement(glosario_root, "INFO")
                ET.SubElement(info, "NAME").text = "Glosario"
                ET.SubElement(info, "INTRO").text = ""
                entries = ET.SubElement(glosario_root, "ENTRIES")
                
                # Iterate rows
                for row in table.find_all('tr'):
                    cells = row.find_all('td')
                    if not cells: continue
                    text = row.get_text().strip()
                    if ":" in text:
                        concept, definition = text.split(":", 1)
                        entry = ET.SubElement(entries, "ENTRY")
                        ET.SubElement(entry, "CONCEPT").text = concept.strip()
                        ET.SubElement(entry, "DEFINITION").text = definition.strip()
                        ET.SubElement(entry, "FORMAT").text = "1"
                        
                # Format XML
                xml_str = ET.tostring(glosario_root, 'utf-8')
                reparsed = minidom.parseString(xml_str)
                pretty_xml = reparsed.toprettyxml(indent="  ")
                
                xml_path = os.path.join(output_dirs["glosario"], "glosario_import.xml")
                with open(xml_path, "w", encoding="utf-8") as f:
                    f.write(pretty_xml)
                logger.info(f"  ✓ Extracted glosario_import.xml with {len(entries)} entries")
                break


    def parse_activity_number(val):
        if val.isdigit():
            return int(val)
        roman = {'I':1,'V':5,'X':10,'L':50,'C':100,'D':500,'M':1000}
        res = 0
        val = val.upper()
        for i in range(len(val)):
            if i + 1 < len(val) and roman.get(val[i], 0) < roman.get(val[i+1], 0):
                res -= roman.get(val[i], 0)
            else:
                res += roman.get(val[i], 0)
        return res

    # 2. Extract Activities and Material de Referencia
    trs = [tr for tr in soup.find_all('tr') if tr.find_parent('table') and not tr.find_parent('table').find_parent('table')]
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
        # Handle cases like "ACTIVIDAD 2.", "ACTIVIDAD II", "ACTIVIDAD 4:"
        if re.match(r'^ACTIVIDAD\s+[\dIVXLCDM]+[\s:.-]*', text) and "ACTIVIDADES DE APRENDIZAJE" not in text and current_unit > 0:
            m = re.search(r'ACTIVIDAD\s+([\dIVXLCDM]+)', text)
            if m:
                raw_activity_number = m.group(1)
                current_activity = parse_activity_number(raw_activity_number)
                act_html_parts = []
                # Include the current row's td contents
                for td in tr.find_all('td'):
                    act_html_parts.append(td.decode_contents())
                
                # Look ahead for following rows belonging to this activity
                i += 1
                while i < len(trs):
                    next_tr = trs[i]
                    next_text = next_tr.get_text().strip().upper()
                    
                    stop_conditions = [
                        re.match(r'^ACTIVIDAD\s+[\dIVXLCDM]+[\s:.-]*', next_text) and "ACTIVIDADES DE APRENDIZAJE" not in next_text,
                        next_text.startswith("UNIDAD DIDÁCTICA") or next_text.startswith("UNIDAD DIDACTICA"),
                        next_text.startswith("CUESTIONARIO"),
                        next_text.startswith("EVALUACIÓN") or next_text.startswith("EVALUACION")
                    ]
                    
                    if any(stop_conditions):
                        # Reached the end of this activity, step back one so the outer loop processes it
                        i -= 1
                        break
                    for td in next_tr.find_all('td'):
                        act_html_parts.append(td.decode_contents())
                    i += 1
                act_html = "".join(act_html_parts)
                
                # Extract Lecturas complementarias / Material de referencia from the activity HTML
                act_soup_mat = BeautifulSoup(act_html, "html.parser")
                header_mat = act_soup_mat.find(lambda t: t.name in ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'strong'] and ('lecturas complementarias' in t.text.lower() or 'material de referencia' in t.text.lower()))
                if header_mat:
                    block_elem = header_mat
                    while block_elem.parent and block_elem.parent.name not in ['td', 'body', 'div', 'tr', '[document]']:
                        block_elem = block_elem.parent
                    
                    mat_parts = []
                    mat_parts.append(str(block_elem))
                    
                    for sibling in block_elem.find_next_siblings():
                        if sibling.name in ['h1', 'h2', 'h3', 'h4', 'h5']:
                            break
                        mat_parts.append(str(sibling))
                    
                    new_mat_html = "".join(mat_parts)
                    unit_num = current_unit if current_unit > 0 else 1
                    mat_file = os.path.join(output_dirs["material"], f"Material_de_referencia_U{unit_num}.html")
                    
                    if os.path.exists(mat_file):
                        with open(mat_file, "r", encoding="utf-8") as f:
                            existing_html = f.read()
                        
                        existing_soup = BeautifulSoup(existing_html, "html.parser")
                        new_soup = BeautifulSoup(new_mat_html, "html.parser")
                        
                        existing_list = existing_soup.find(['ul', 'ol'])
                        new_lists = new_soup.find_all(['ul', 'ol'])
                        
                        if existing_list and new_lists:
                            for new_list in new_lists:
                                for li in new_list.find_all('li', recursive=False):
                                    existing_list.append(li)
                        else:
                            # If we couldn't find lists to merge, just append non-header elements
                            for tag in new_soup.contents:
                                if tag.name and tag.name.lower() in ['p', 'strong'] and ('lecturas complementarias' in tag.get_text().lower() or 'material de referencia' in tag.get_text().lower()):
                                    continue
                                existing_soup.append(tag)
                                
                        with open(mat_file, "w", encoding="utf-8") as f:
                            f.write(str(existing_soup))
                    else:
                        with open(mat_file, "w", encoding="utf-8") as f:
                            f.write(new_mat_html)
                            
                    logger.info(f"  ✓ SUCCESS: Extracted 'Lecturas complementarias' (Material de referencia) for 'Actividad {raw_activity_number}'")
                    logger.info(f"    - Merged into: {os.path.basename(mat_file)} (Unidad {unit_num})")
                else:
                    logger.debug(f"  - No 'Lecturas complementarias' or 'Material de referencia' found for Actividad {raw_activity_number}")
                
                act_soup = BeautifulSoup(act_html, "html.parser")
                
                # Remove the title of the "Actividad" (e.g. ACTIVIDAD 1: ...)
                title_pattern = re.compile(rf'ACTIVIDAD\s+{re.escape(raw_activity_number)}[\s:.-]*', re.IGNORECASE)
                for text_node in act_soup.find_all(string=title_pattern):
                    parent = text_node.find_parent(['p', 'h1', 'h2', 'h3', 'h4'])
                    if parent:
                        parent.decompose()
                    else:
                        p = text_node.parent
                        if p:
                            p.decompose()

                # Convert remaining h1, h2, h3 to <p><b>...</b></p>
                for header in act_soup.find_all(['h1', 'h2', 'h3']):
                    new_p = act_soup.new_tag("p")
                    new_b = act_soup.new_tag("b")
                    # Preserve contents by moving them
                    new_b.extend(header.contents)
                    new_p.append(new_b)
                    header.replace_with(new_p)
                
                act_html_transformed = str(act_soup)
                
                base_act_name = f"actividad{current_activity}"
                act_file_name = f"{base_act_name}.html"
                act_file_path = os.path.join(output_dirs["actividades"], act_file_name)
                
                counter = 1
                while os.path.exists(act_file_path):
                    act_file_name = f"{base_act_name}_{counter}.html"
                    act_file_path = os.path.join(output_dirs["actividades"], act_file_name)
                    counter += 1
                
                with open(act_file_path, "w", encoding="utf-8") as f:
                    f.write(act_html_transformed)
                logger.info(f"  ✓ Extracted {act_file_name}")
        else:
            # Not a unit, not an activity.
            pass
        i += 1

    logger.info("  ✓ DOCX splitting workflow completed.")
