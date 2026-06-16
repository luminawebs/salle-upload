import os
import re
import base64
import logging
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

TEXT_SPAN_STYLE = "font-family: tahoma, arial, helvetica, sans-serif; font-size: small; color: #000000;"
RUBRIC_HEADER_STYLE = "background-color: #e7b917;"

def get_image_base64(image_filename: str, course_id: int = None) -> str:
    image_path = None
    
    # Try course specific images first
    if course_id:
        course_img = os.path.join("assets", str(course_id), "imgs", image_filename)
        if os.path.exists(course_img):
            image_path = course_img

    if not image_path:
        # Try shared assets
        shared_img = os.path.join("assets", "shared", image_filename)
        if os.path.exists(shared_img):
            image_path = shared_img
            
    if not image_path:
        # Fallback to example_course
        example_img = os.path.join("assets", "example_course", image_filename)
        if os.path.exists(example_img):
            image_path = example_img
            
    if not image_path:
        # Also try the raw filename if it exists
        if os.path.exists(image_filename):
            image_path = image_filename
        else:
            logger.warning(f"Transformer image not found: {image_filename}")
            return ""
        
    try:
        with open(image_path, "rb") as img_file:
            encoded_string = base64.b64encode(img_file.read()).decode('utf-8')
        
        ext = os.path.splitext(image_filename)[1].lower().replace('.', '')
        mime_type = f"image/{ext}" if ext in ['png', 'jpg', 'jpeg', 'gif'] else "image/png"
        
        return f"data:{mime_type};base64,{encoded_string}"
    except Exception as e:
        logger.error(f"Failed to encode image {image_path}: {e}")
        return ""

def extract_questions_from_html_to_gift(html_content: str, output_txt_path: str) -> bool:
    """
    Finds questions in HTML (either via <ol> DOM structures or 'Pregunta N' blocks)
    and exports them to a GIFT file.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    gift_lines = []
    
    # NEW ROBUST LOGIC (DOM Based)
    ols = soup.find_all('ol')
    q_num = 1
    for ol in ols:
        correct_p = ol.find_next_sibling('p')
        if correct_p:
            correct_text_full = correct_p.get_text(strip=True)
            if "Respuesta correcta:" in correct_text_full or "Respuestas correctas:" in correct_text_full:
                correct_text = correct_text_full.replace("Respuesta correcta:", "").replace("Respuestas correctas:", "").strip()
                
                # Extract feedback
                feedback_text = ""
                feedback_p = correct_p.find_next_sibling('p')
                if feedback_p:
                    feedback_text_full = feedback_p.get_text(strip=True)
                    if "Retroalimentación:" in feedback_text_full or "Retroalimentación incorrecta:" in feedback_text_full:
                        feedback_text = feedback_text_full.replace("Retroalimentación incorrecta:", "").replace("Retroalimentación:", "").strip()
                
                # Extract stem and options
                lis = ol.find_all('li')
                if not lis:
                    continue
                
                stem = lis[0].get_text(strip=True)
                options = [li.get_text(strip=True) for li in lis[1:]]
                
                is_true_false = False
                gift_ans = ""
                
                if len(options) == 0:
                    is_true_false = True
                elif len(options) == 2:
                    opt_lower = [o.lower() for o in options]
                    if any("verdadero" in o or "true" in o for o in opt_lower) and any("falso" in o or "false" in o for o in opt_lower):
                        is_true_false = True
                        
                if is_true_false or "verdadero" in correct_text.lower() or "falso" in correct_text.lower():
                    is_true = "verdadero" in correct_text.lower() or "true" in correct_text.lower()
                    gift_ans = "T" if is_true else "F"
                    
                    q_num_padded = f'{q_num:02d}'
                    gift = f'// Pregunta {q_num_padded}\n::Pregunta {q_num_padded}::{stem} {{{gift_ans}'
                    if feedback_text:
                        gift += f'####{feedback_text}'
                    gift += '}'
                    gift_lines.append(gift)
                    q_num += 1
                else:
                    q_num_padded = f'{q_num:02d}'
                    gift = f'// Pregunta {q_num_padded}\n::Pregunta {q_num_padded}::{stem} {{\n'
                    for opt in options:
                        opt_norm = opt.lower().strip('. ')
                        correct_norm = correct_text.lower().strip('. ')
                        
                        is_correct = opt_norm in correct_norm or correct_norm in opt_norm
                        prefix = '=' if is_correct else '~'
                        gift += f'\t{prefix}{opt}\n'
                        
                    if feedback_text:
                        gift += f'####{feedback_text}\n'
                    gift += '}'
                    gift_lines.append(gift)
                    q_num += 1

    # FALLBACK LOGIC
    if not gift_lines:
        paragraphs = soup.find_all(["p", "li", "div", "span"])
        lines = []
        for p in paragraphs:
            text = p.get_text(strip=True)
            if text:
                if not p.find_parent(["p", "li"]):
                    lines.append(text)
                    
        text = '\n'.join(lines)
        
        # Split by 'Pregunta N:'
        questions = re.split(r'(?i)^(Pregunta\s+(\d+):?)\s*$', text, flags=re.MULTILINE)
        
        if len(questions) >= 3:
            for i in range(1, len(questions), 3):
                if i + 2 >= len(questions):
                    break
                    
                q_label = questions[i].strip()
                old_q_num = questions[i+1].strip()
                q_body = questions[i+2].strip()
                
                body_lines = [l.strip() for l in q_body.split('\n') if l.strip()]
                if not body_lines:
                    continue
                    
                stem = body_lines[0]
                options_lines = body_lines[1:]
                
                options = []
                for opt_line in options_lines:
                    if opt_line.lower().startswith("explicación:") or opt_line.lower().startswith("explicacion:"):
                        break
                        
                    if re.search(r'\([xX]\)$', opt_line):
                        is_correct = True
                        opt_text = re.sub(r'\([xX]\)$', '', opt_line).strip()
                    else:
                        is_correct = False
                        opt_text = opt_line
                        
                    prefix = '=' if is_correct else '~'
                    options.append(f'\t{prefix}{opt_text}')
                    
                try:
                    q_num_padded = f'{int(old_q_num):02d}'
                except ValueError:
                    q_num_padded = old_q_num
                    
                gift = f'// {q_label}\n::P{q_num_padded}::{stem} {{\n'
                for opt in options:
                    gift += f'{opt}\n'
                gift += '}\n'
                gift_lines.append(gift)

    if not gift_lines:
        return False
        
    try:
        with open(output_txt_path, 'w', encoding='utf-8') as f:
            f.write('\n\n'.join(gift_lines))
        logger.info(f"Successfully created {output_txt_path} with {len(gift_lines)} questions.")
        return True
    except Exception as e:
        logger.error(f"Failed to write GIFT file {output_txt_path}: {e}")
        return False

def remove_questions_from_html(html_content: str) -> str:
    """
    Removes the questions block from the HTML.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    start_deleting = False
    elements_to_delete = []
    
    for el in soup.find_all(["p", "div", "ul", "ol"]):
        text = el.get_text(strip=True)
        if re.search(r'(?i)^Pregunta\s+1:?', text):
            start_deleting = True
            
        if "Cómo lo vamos a evaluar" in text or "Criterios de desempeño" in text:
            start_deleting = False
            
        if start_deleting:
            elements_to_delete.append(el)
            
    for el in elements_to_delete:
        el.decompose()
        
    # Remove text indicating questions origin
    for p in soup.find_all("p"):
        if "siguientes preguntas fue extra" in p.get_text():
            p.decompose()
            
    return str(soup)

def transform_activity_html(html_content: str, course_id: int = None) -> str:
    if not html_content or not html_content.strip():
        return html_content
        
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 1. Remove the first paragraph that contains the Activity Title
    for p in soup.find_all("p"):
        if "ACTIVIDAD" in p.get_text().upper() and ":" in p.get_text():
            p.decompose()
            break
            
    # 2. Replace headings with images
    heading_map = {
        "¿Qué vamos a lograr?": "eti-actividades.png",
        "¿Cómo lo vamos a lograr?": "eti-actividades-b.png",
        "¿Cómo lo vamos a evaluar?": "banner_evaluacion.png"
    }
    
    eval_header_p = None
    for p in soup.find_all("p"):
        text = p.get_text(" ", strip=True)
        # Check against heading map
        matched = False
        for target_text, img_file in heading_map.items():
            if target_text in text:
                if target_text == "¿Cómo lo vamos a evaluar?":
                    eval_header_p = p
                base64_data = get_image_base64(img_file, course_id)
                if base64_data:
                    p.clear()
                    img_tag = soup.new_tag("img", src=base64_data, width="60%")
                    p.append(img_tag)
                matched = True
                break
                
    # 2.5 Clean up everything after the Evaluation banner except the table
    if eval_header_p:
        curr = eval_header_p.find_next_sibling()
        while curr:
            next_sib = curr.find_next_sibling()
            if curr.name != "table":
                curr.decompose()
            curr = next_sib
            
    # 2.7 Convert local images from the document (like from /imgs folder) to base64
    for img in soup.find_all("img"):
        src = img.get("src")
        if src and not str(src).startswith("data:") and not str(src).startswith("http"):
            filename = os.path.basename(str(src))
            base64_data = get_image_base64(filename, course_id)
            if base64_data:
                img["src"] = base64_data
        
    # 3. Format URLs
    for a_tag in soup.find_all("a"):
        # Set target attribute
        a_tag['target'] = "_blank"
        
        # Change the link text
        a_tag.string = "(disponible aquí)"
        
        # Optionally clean up a preceding colon in the text right before the link
        prev_node = a_tag.previous_sibling
        if prev_node and isinstance(prev_node, str) and prev_node.strip().endswith(":"):
            # Remove the colon
            new_text = prev_node.rstrip()[:-1] + " "
            prev_node.replace_with(new_text)
            
    # 4. Apply Typography (wrap text in spans)
    for tag in soup.find_all(["p", "li"]):
        if tag.find("img"):
            continue
            
        if not tag.find("span", style=TEXT_SPAN_STYLE):
            new_span = soup.new_tag("span", style=TEXT_SPAN_STYLE)
            for child in list(tag.contents):
                new_span.append(child.extract())
            tag.append(new_span)
            
    # 4. Format the Rubric Table
    tables = soup.find_all("table")
    for table in tables:
        if "Criterios de desempeño" in table.get_text():
            table['style'] = "width: 60%;"
            table['border'] = "1"
            table['cellspacing'] = "0"
            table['cellpadding'] = "0"
            
            div_wrapper = soup.new_tag("div", align="center")
            table.wrap(div_wrapper)
            
            rows = table.find_all("tr")
            for i, row in enumerate(rows):
                tds = row.find_all(["td", "th"])
                
                # Header row
                if i == 0:
                    row['style'] = RUBRIC_HEADER_STYLE
                    for td in tds:
                        td['valign'] = "top"
                        if "Criterios" in td.get_text():
                            td['width'] = "436"
                            inner_p = td.find("p")
                            if inner_p: inner_p['align'] = "center"
                        else:
                            td['width'] = "48"
                            inner_p = td.find("p")
                            if inner_p: inner_p['align'] = "center"
                            
                # Data rows
                elif i < len(rows) - 1:
                    for j, td in enumerate(tds):
                        td['valign'] = "top"
                        if j == 0:
                            td['width'] = "436"
                            inner_p = td.find("p")
                            if inner_p: inner_p['align'] = "left"
                        else:
                            td['width'] = "48"
                            td['style'] = "text-align: center;"
                            inner_p = td.find("p")
                            if inner_p: 
                                inner_p['align'] = "right"
                                # Replace integer score with comma decimal
                                txt = inner_p.get_text(strip=True)
                                if txt.isdigit():
                                    for t_node in inner_p.find_all(string=True):
                                        t_node.replace_with(t_node.replace(txt, f"{txt},0"))
                                
                # Footer row
                else:
                    for j, td in enumerate(tds):
                        td['valign'] = "top"
                        if j == 0:
                            td['width'] = "436"
                            inner_p = td.find("p")
                            if inner_p:
                                inner_p['align'] = "right"
                                # Replace "La suma total debe dar" with "Total"
                                for t_node in inner_p.find_all(string=True):
                                    if "La suma total" in t_node:
                                        t_node.replace_with("Total")
                        else:
                            td['width'] = "48"
                            td['style'] = "text-align: center;"
                            inner_p = td.find("p")
                            if inner_p:
                                inner_p['align'] = "right"
                                txt = inner_p.get_text(strip=True)
                                if txt.isdigit():
                                    for t_node in inner_p.find_all(string=True):
                                        t_node.replace_with(t_node.replace(txt, f"{txt},0"))
                                        
    # The trailing duplicated rubric text fix is now handled by step 2.5

    # Also clean up empty <p><strong></strong></p> after replacements
    for p in soup.find_all("p"):
        if not p.get_text(strip=True) and not p.find("img"):
            p.decompose()
            
    return str(soup)


def generate_dynamic_generalidades_html(extracted_html_path, template_path):
    with open(extracted_html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')

    presentacion_html = ""
    metodologia_html = ""
    docente_html = ""
    plan_html = ""

    # Extract Presentación
    for el in soup.find_all(['p', 'h1', 'h2', 'h3']):
        if 'PRESENTACIÓN DEL ESPACIO ACADÉMICO' in el.get_text().upper() or 'PRESENTACION DEL ESPACIO ACADEMICO' in el.get_text().upper():
            nxt = el.find_next_sibling()
            blocks = []
            while nxt and nxt.name not in ['h1', 'h2', 'table']:
                if 'OPCIÓN METODOLÓGICA' in nxt.get_text().upper() or 'PLAN DE FORMACIÓN' in nxt.get_text().upper():
                    break
                blocks.append(str(nxt))
                nxt = nxt.find_next_sibling()
            presentacion_html = "".join(blocks)
            break

    # Extract Metodología
    for el in soup.find_all(['p', 'h1', 'h2', 'h3']):
        if 'OPCIÓN METODOLÓGICA DEL ESPACIO ACADÉMICO' in el.get_text().upper() or 'OPCION METODOLOGICA' in el.get_text().upper():
            nxt = el.find_next_sibling()
            blocks = []
            while nxt and nxt.name not in ['h1', 'h2', 'table']:
                if 'PRESENTACIÓN DEL' in nxt.get_text().upper() or 'PLAN DE FORMACIÓN' in nxt.get_text().upper():
                    break
                blocks.append(str(nxt))
                nxt = nxt.find_next_sibling()
            metodologia_html = "".join(blocks)
            break

    # Extract Equipo Docente
    table = soup.find('table')
    if table:
        nombres = ""
        perfil = ""
        correo = ""
        foto = ""
        for tr in table.find_all('tr'):
            text = tr.get_text(separator=' ', strip=True).lower()
            if 'nombres y apellidos' in text:
                tds = tr.find_all('td')
                if len(tds) > 1: nombres = tds[1].get_text(strip=True)
            elif 'perfil profesional' in text:
                tds = tr.find_all('td')
                if len(tds) > 1: perfil = tds[1].get_text(strip=True)
            elif 'correo electr' in text:
                tds = tr.find_all('td')
                if len(tds) > 1: correo = tds[1].get_text(strip=True)
            elif 'foto' in text:
                tds = tr.find_all('td')
                if len(tds) > 1:
                    img = tds[1].find('img')
                    if img and img.get('src'):
                        foto = img['src']

        docente_html = f'''
        <div class="card-body" style="text-align: center;">
            <span style="font-size: 1rem;">
                {"<img class='img-fluid' src='" + foto + "' width='350' height='400'>" if foto else ""}
            </span>
        </div>
        <div class="card-body" style="text-align: center;">
            <strong><span style="font-size: medium; font-family: tahoma, arial, helvetica, sans-serif; color: #000000;">{nombres}</span></strong>
        </div>
        <div class="card-body">
            <span style="font-family: tahoma, arial, helvetica, sans-serif; font-size: small; color: #000000;">
                {perfil}<br/><br/>
                <strong>Contacto:</strong> {correo}
            </span>
        </div>
        '''

    def format_plan_de_formacion_table(table_tag, main_soup):
        table_tag['class'] = "MsoTableGrid"
        table_tag['style'] = "width: 100%; border-collapse: collapse; border: 1px solid #000; font-family: Arial, sans-serif; font-size: 10pt; color: #000; text-align: center;"
        table_tag['border'] = "1"
        table_tag['cellspacing'] = "0"
        table_tag['cellpadding'] = "0"
        
        rows = table_tag.find_all('tr')
        col_widths_6 = ["9.78%", "14.2%", "19.62%", "31.74%", "15.18%", "9.48%"]
        col_widths_3 = ["31.74%", "15.18%", "9.48%"]
        
        for r_idx, row in enumerate(rows):
            cells = row.find_all(['td', 'th'])
            
            if r_idx == 0 and len(cells) == 1:
                cells[0]['style'] = "border: 1px solid #000; background: #f2a900; padding: 5px; font-weight: bold; font-size: 12pt;"
                for p in cells[0].find_all('p'):
                    p['style'] = "text-align: center;"
                continue
                
            if r_idx == 1 and len(cells) >= 5:
                for c_idx, cell in enumerate(cells):
                    w = col_widths_6[c_idx] if c_idx < len(col_widths_6) else "auto"
                    cell['style'] = f"border: 1px solid #000; background: #fac96a; font-weight: bold; padding: 5px; width: {w};"
                continue
                
            is_encuentro = "encuentro virtual" in row.get_text().lower()
            bg_color = "#fdfdec" if is_encuentro else "#fff"
            widths = col_widths_6 if len(cells) >= 5 else col_widths_3
            
            for c_idx, cell in enumerate(cells):
                w = widths[c_idx] if c_idx < len(widths) else "auto"
                is_activity_col = (len(cells) <= 3) or (c_idx >= 3)
                cell_bg = bg_color if is_activity_col else "#fff"
                
                align = "left" if (is_activity_col and c_idx == (0 if len(cells) <= 3 else 3)) else "center"
                if len(cell.get_text(strip=True)) > 20:
                    align = "left"
                    
                cell['style'] = f"border: 1px solid #000; background: {cell_bg}; padding: 5px; text-align: {align}; vertical-align: top; width: {w};"
                
                for heading in cell.find_all(['h1', 'h2', 'h3', 'h4']):
                    new_p = main_soup.new_tag('p')
                    strong = main_soup.new_tag('strong')
                    strong.append(heading.get_text())
                    new_p.append(strong)
                    heading.replace_with(new_p)
                    
                for p in cell.find_all('p'):
                    if p.has_attr('style'): del p['style']
                    if p.has_attr('align'): del p['align']
                    if p.has_attr('class'): del p['class']
                    
    # Extract Plan de Formación
    tables = soup.find_all('table')
    for t in tables:
        if 'PLAN DE FORMACIÓN' in t.get_text().upper() or 'PLAN DE FORMACION' in t.get_text().upper():
            # Remove "(clic para ver ejemplos)" text/links
            for el in t.find_all(string=re.compile(r"clic para ver ejemplos", re.IGNORECASE)):
                parent_p = el.find_parent('p')
                if parent_p:
                    parent_p.decompose()
                else:
                    parent_a = el.find_parent('a')
                    if parent_a:
                        parent_a.decompose()
                    else:
                        el.extract()
            format_plan_de_formacion_table(t, soup)
            plan_html = str(t)
            break

    if not foto:
        import logging
        logger = logging.getLogger(__name__)
        logger.info("No se ha proporcionado imagen del docente. No image placeholder will be added.")

    # Inject into template
    with open(template_path, 'r', encoding='utf-8') as f:
        template = f.read()

    def replace_section(html, start_marker, end_marker, replacement):
        # Allow spaces/newlines in markers
        sm = start_marker.replace(" ", r"\s*")
        em = end_marker.replace(" ", r"\s*")
        pattern = re.compile(rf'(<p[^>]*class="hide"[^>]*>.*?{sm}.*?</p>)(.*?)(<p[^>]*class="hide"[^>]*>.*?{em}.*?</p>)', re.DOTALL | re.IGNORECASE)
        # Note: we need to wrap the replacement in a lambda so backreferences in replacement text aren't parsed
        # By just returning the replacement, we omit the marker paragraphs (m.group(1) and m.group(3))
        return pattern.sub(lambda m: replacement, html)

    template = replace_section(template, 'Inicio texto presentación', 'Fin texto de presentación', presentacion_html)
    template = replace_section(template, 'Inicio texto Metodología', 'Fin texto Metodología', metodologia_html)
    template = replace_section(template, 'Inicio presentación del docente', 'Fin presentación del docente', docente_html)
    template = replace_section(template, 'Inicio texto Plan del curso', 'Fin texto Plan del curso', plan_html)

    # Note: there is a slight typo in the generalidades html for the end of presentacion, it says 'Fin texto de presentación'.
    # And for Metodologia it says 'Inicio texto Metodología'.



    return template

