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

def process_image_src(html_str, course_id=None):
    if not html_str: return ""
    soup = BeautifulSoup(html_str, 'html.parser')
    for img in soup.find_all('img'):
        src = img.get('src')
        if src and not str(src).startswith('data:'):
            filename = os.path.basename(str(src))
            base64_data = get_image_base64(filename, course_id)
            if base64_data:
                img['src'] = base64_data
            img['style'] = "max-width: 100%; height: auto;"
    return soup.decode_contents()

def extract_questions_from_html_to_moodle_xml(html_content: str, output_xml_path: str = None, course_id: int = None, document_name: str = "doc") -> int:
    """
    Finds questions in HTML and exports them to a Moodle XML file retaining full HTML.
    Uses a robust block-level state machine parser.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # --- 1. DOM FLATTENING ---
    blocks = []
    def traverse(node, list_level=0, list_group_id=None):
        if isinstance(node, str):
            text = node.strip()
            if text:
                blocks.append({'type': 'text', 'html': str(node), 'text': text, 'list_level': list_level, 'list_group_id': list_group_id})
            return
            
        if getattr(node, 'name', None) in ['ul', 'ol']:
            new_group_id = id(node)
            for child in node.children:
                traverse(child, list_level + 1, new_group_id)
            return
            
        if getattr(node, 'name', None) == 'li':
            current_html = []
            current_text = []
            
            def flush_li():
                if current_html:
                    html_str = "".join(current_html)
                    text_str = "".join(current_text).strip()
                    if text_str or "img" in html_str or "table" in html_str:
                        blocks.append({'type': 'li', 'html': html_str, 'text': text_str, 'list_level': list_level, 'list_group_id': list_group_id})
                    current_html.clear()
                    current_text.clear()

            for child in node.children:
                if getattr(child, 'name', None) in ['ul', 'ol']:
                    flush_li()
                    traverse(child, list_level + 1, id(child))
                else:
                    if isinstance(child, str):
                        current_html.append(str(child))
                        current_text.append(str(child))
                    elif child.name == 'img':
                        processed_img = process_image_src(str(child), course_id)
                        current_html.append(processed_img)
                        current_text.append("")
                    else:
                        processed_html = process_image_src(str(child), course_id)
                        current_html.append(processed_html)
                        current_text.append(child.get_text(separator=" "))
            flush_li()
            return

        if getattr(node, 'name', None) in ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div', 'span']:
            processed_html = process_image_src(str(node), course_id)
            text = node.get_text(separator=" ", strip=True)
            if text or "img" in processed_html or "table" in processed_html:
                blocks.append({'type': node.name, 'html': processed_html, 'text': text, 'list_level': list_level, 'list_group_id': list_group_id})
            return
            
        if getattr(node, 'name', None) == 'table':
            processed_html = process_image_src(str(node), course_id)
            blocks.append({'type': 'table', 'html': processed_html, 'text': node.get_text(separator=" ", strip=True), 'list_level': list_level, 'list_group_id': list_group_id})
            return
            
        if getattr(node, 'name', None) == 'img':
            processed_html = process_image_src(str(node), course_id)
            blocks.append({'type': 'img', 'html': processed_html, 'text': '', 'list_level': list_level, 'list_group_id': list_group_id})
            return
            
        # Fallback for other tags
        if hasattr(node, 'children'):
            for child in node.children:
                traverse(child, list_level, list_group_id)

    traverse(soup)

    # --- Pre-calculate option groups ---
    option_groups = set()
    for block in blocks:
        if block['list_group_id']:
            text = block['text']
            if re.match(r'^=?[A-Ea-e][\.\)\-]\s*', text) or text.lower().startswith('verdadero') or text.lower().startswith('falso'):
                option_groups.add(block['list_group_id'])
            elif "(respuesta" in text.lower() or "(correct answer)" in text.lower() or re.search(r'\([xX]\)$', text):
                option_groups.add(block['list_group_id'])
            elif text.strip().startswith('='):
                option_groups.add(block['list_group_id'])

    # --- 2. STATE MACHINE PARSER ---
    questions = []
    current_q = None
    state = 'SEARCHING' # SEARCHING, STEM, OPTIONS, FEEDBACK
    
    def save_q():
        if current_q and current_q['stem_html'] and current_q['options']:
            questions.append(current_q)
            
    def create_empty_q():
        return {
            'stem_html': [],
            'options': [],
            'feedback': {'general': [], 'correct': [], 'incorrect': []},
            'base_list_level': 0,
            'active_fb_type': 'general'
        }

    for block in blocks:
        text = block['text']
        b_type = block['type']
        html_str = block['html']
        l_level = block['list_level']
        l_group_id = block['list_group_id']

        # Skip empty text blocks unless they have media
        if not text and b_type not in ['img', 'table'] and "img" not in html_str and "table" not in html_str:
            continue

        # 2a. Check if Feedback
        is_feedback_header = text.lower().startswith('retroalimentaci') or text.lower().startswith('explicaci')
        if is_feedback_header:
            if "correcta" in text.lower() and "incorrecta" not in text.lower():
                fb_type = "correct"
            elif "incorrecta" in text.lower():
                fb_type = "incorrect"
            else:
                fb_type = "general"
                
            clean_html = re.sub(r'(?i)^(?:<[^>]+>)*\s*(?:retroalimentaci[^:]*:|explicaci[^:]*:)\s*(?:</[^>]+>)*', '', html_str).strip()
            
            if current_q:
                state = 'FEEDBACK'
                current_q['active_fb_type'] = fb_type
                if clean_html:
                    current_q['feedback'][fb_type].append(clean_html)
            continue
            
        # 2b. Check if Option
        is_option = False
        is_correct = False
        clean_html_opt = html_str
        
        if b_type != 'table' and b_type != 'img':
            if re.match(r'^=?[A-Ea-e][\.\)\-]\s*', text) or text.lower().startswith('verdadero') or text.lower().startswith('falso'):
                is_option = True
            elif "(respuesta" in text.lower() or "(correct answer)" in text.lower() or re.search(r'\([xX]\)$', text):
                is_option = True
            elif text.strip().startswith('='):
                is_option = True
            # Check list group
            elif l_group_id and l_group_id in option_groups:
                is_option = True

        if is_option and current_q:
            if re.search(r'\([xX]\)$', text):
                is_correct = True
                clean_html_opt = re.sub(r'\([xX]\)(?=[^>]*(?:<|$))', '', clean_html_opt).strip()
            elif text.strip().startswith('='):
                is_correct = True
                clean_html_opt = re.sub(r'^\s*=\s*(?=[^>]*(?:<|$))', '', clean_html_opt).strip()
            elif "(respuesta" in text.lower() or "(correct answer)" in text.lower():
                is_correct = True
                clean_html_opt = re.sub(r'(?i)\s*\((?:respuesta(?: correcta)?|correct answer)\)', '', clean_html_opt).strip()
                
            if state in ['SEARCHING', 'STEM']:
                state = 'OPTIONS'
            current_q['options'].append({'html': clean_html_opt, 'is_correct': is_correct})
            continue

        # 2c. Check if Question Start
        is_start = False
        if b_type not in ['table', 'img']:
            if re.match(r'^(?:Pregunta\s+)?\d+[\.:]?\s*', text, re.IGNORECASE):
                is_start = True
            elif text.startswith('¿'):
                if state in ['OPTIONS', 'FEEDBACK'] or current_q is None:
                    is_start = True
            elif state in ['OPTIONS', 'FEEDBACK'] and b_type in ['p', 'div'] and not is_option:
                if len(text.split()) > 5:
                    is_start = True
                    
        if is_start:
            save_q()
            current_q = create_empty_q()
            current_q['base_list_level'] = l_level
            state = 'STEM'
            current_q['stem_html'].append(html_str)
            continue
            
        # 2d. Append to current state
        if current_q:
            if state == 'STEM':
                current_q['stem_html'].append(html_str)
            elif state == 'OPTIONS':
                if current_q['options']:
                    current_q['options'][-1]['html'] += f"<br>{html_str}"
                else:
                    current_q['stem_html'].append(html_str)
            elif state == 'FEEDBACK':
                fb_type = current_q['active_fb_type']
                current_q['feedback'][fb_type].append(html_str)

    save_q()
    
    import time
    parser_start_time = time.perf_counter()
    parser_end_time = time.perf_counter()

    # --- 3. BUILD XML STRINGS ---
    xml_questions = []
    structured_questions = []
    xml_header = '<?xml version="1.0" encoding="UTF-8"?>\n<quiz>\n'
    xml_footer = '</quiz>\n'
    
    def add_question(q_num, stem_html, options, is_true_false, correct_is_true, fb_gen="", fb_corr="", fb_inc=""):
        q_dict = {
            "stem_html": stem_html,
            "options": [],
            "correct_feedback_html": fb_corr or fb_gen,
            "incorrect_feedback_html": fb_inc or fb_gen
        }
        
        q_xml = f'<!-- question: {q_num}  -->\n'
        q_type = 'truefalse' if is_true_false else 'multichoice'
        q_xml += f'  <question type="{q_type}">\n'
        q_xml += f'    <name>\n      <text><![CDATA[{course_id}_{document_name}_q{q_num}]]></text>\n    </name>\n'
        q_xml += f'    <questiontext format="html">\n      <text><![CDATA[{stem_html}]]></text>\n    </questiontext>\n'
        if fb_gen:
            q_xml += f'    <generalfeedback format="html">\n      <text><![CDATA[{fb_gen}]]></text>\n    </generalfeedback>\n'
        if fb_corr:
            q_xml += f'    <correctfeedback format="html">\n      <text><![CDATA[{fb_corr}]]></text>\n    </correctfeedback>\n'
        if fb_inc:
            q_xml += f'    <incorrectfeedback format="html">\n      <text><![CDATA[{fb_inc}]]></text>\n    </incorrectfeedback>\n'
        q_xml += '    <defaultgrade>1.0000000</defaultgrade>\n'
        q_xml += '    <penalty>0.3333333</penalty>\n'
        q_xml += '    <hidden>0</hidden>\n'
        
        if is_true_false:
            q_xml += f'    <answer fraction="{"100" if correct_is_true else "0"}" format="moodle_auto_format">\n      <text>true</text>\n    </answer>\n'
            q_xml += f'    <answer fraction="{"0" if correct_is_true else "100"}" format="moodle_auto_format">\n      <text>false</text>\n    </answer>\n'
            q_dict["options"].append({"text_html": "true", "is_correct": correct_is_true})
            q_dict["options"].append({"text_html": "false", "is_correct": not correct_is_true})
        else:
            q_xml += '    <single>true</single>\n'
            q_xml += '    <shuffleanswers>true</shuffleanswers>\n'
            q_xml += '    <answernumbering>abc</answernumbering>\n'
            for opt_html, is_correct in options:
                fraction = "100" if is_correct else "0"
                opt_soup = BeautifulSoup(opt_html, 'html.parser')
                first_text = opt_soup.find(string=True)
                if first_text:
                    new_text = re.sub(r'^\s*=?\s*[a-zA-Z][\.\)]\s*', '', first_text)
                    if new_text != first_text:
                        first_text.replace_with(new_text)
                        opt_html = str(opt_soup)
                q_dict["options"].append({"text_html": opt_html, "is_correct": is_correct})
                q_xml += f'    <answer fraction="{fraction}" format="html">\n      <text><![CDATA[{opt_html}]]></text>\n    </answer>\n'
                
        q_xml += '  </question>\n'
        xml_questions.append(q_xml)
        structured_questions.append(q_dict)

    q_num = 1
    for q in questions:
        stem_html = "<br>".join(q['stem_html'])
        opts = []
        is_true_false = False
        correct_is_true = False
        
        for o in q['options']:
            opts.append((o['html'], o['is_correct']))
            
        opt_texts = [BeautifulSoup(o[0], 'html.parser').get_text(strip=True).lower() for o in opts]
        if len(opt_texts) == 2:
            if any(x in txt for txt in opt_texts for x in ['verdadero', 'true']) and any(x in txt for txt in opt_texts for x in ['falso', 'false']):
                is_true_false = True
                for o_html, is_corr in opts:
                    if is_corr and any(x in o_html.lower() for x in ['verdadero', 'true']):
                        correct_is_true = True
                        
        fb_gen = "<br>".join(q['feedback']['general'])
        fb_corr = "<br>".join(q['feedback']['correct'])
        fb_inc = "<br>".join(q['feedback']['incorrect'])
        
        add_question(q_num, stem_html, opts, is_true_false, correct_is_true, fb_gen, fb_corr, fb_inc)
        q_num += 1

    # --- 4. VALIDATION LOGIC (AI QA Layer) ---
    standard_q_count = len(xml_questions)
    should_invoke_ai = False
    
    if standard_q_count > 0:
        logger.info(f"Standard parser detected {standard_q_count} questions. Starting AI Validation...")
        should_invoke_ai = True
    elif "cuestionario" in html_content.lower() or "evaluemos" in html_content.lower() or "pregunta " in html_content.lower():
        logger.info("Standard parser found 0 questions but keywords indicate a questionnaire. Starting AI Validation as fallback...")
        should_invoke_ai = True

    if should_invoke_ai:
        ai_start_time = time.perf_counter()
        try:
            import json
            from core.ai_structurer import validate_and_extract_questions
            serialized_parser_output = json.dumps(structured_questions, ensure_ascii=False)
            
            ai_result = validate_and_extract_questions(html_content, serialized_parser_output, parsed_q_count=standard_q_count)
            ai_end_time = time.perf_counter()
            
            is_perfect = False
            corrections = []
            additions = []
            removals = []
            metadata = {}
            token_usage = {}
            status_text = "SUCCESS"
            
            if "error" in ai_result:
                status_text = f"FAILED_FALLBACK ({ai_result['error']})"
                logger.error(f"AI QA Layer returned error or exhausted retries: {ai_result['error']}. Falling back to standard parser.")
            else:
                is_perfect = ai_result.get("is_perfect", False)
                corrections = ai_result.get("corrections", [])
                additions = ai_result.get("additions", [])
                removals = ai_result.get("removals", [])
                metadata = ai_result.get("metadata", {})
                token_usage = ai_result.get("token_usage", {})
                
                final_questions = list(structured_questions)
                
                for idx in sorted(removals, reverse=True):
                    if 0 <= idx < len(final_questions):
                        del final_questions[idx]
                        
                for corr in corrections:
                    idx = corr.get("index")
                    if idx is not None and 0 <= idx < len(final_questions):
                        final_questions[idx] = corr.get("corrected_question", final_questions[idx])
                        
                for add in additions:
                    final_questions.append(add)
                
                xml_questions.clear()
                structured_questions.clear()
                
                q_num_rebuild = 1
                for q in final_questions:
                    stem = q.get("stem_html", "")
                    opts = []
                    for opt in q.get("options", []):
                        opts.append((opt.get("text_html", ""), opt.get("is_correct", False)))
                    correct_fb = q.get("correct_feedback_html", "")
                    incorrect_fb = q.get("incorrect_feedback_html", "")
                    
                    is_tf = False
                    correct_is_true = False
                    if len(opts) == 2:
                        opt_texts_lower = [o[0].lower() for o in opts]
                        if any(x in o for o in opt_texts_lower for x in ['verdadero', 'true']) and any(x in o for o in opt_texts_lower for x in ['falso', 'false']):
                            is_tf = True
                            for opt_text, is_corr in opts:
                                if is_corr and ('verdadero' in opt_text.lower() or 'true' in opt_text.lower()):
                                    correct_is_true = True
                    
                    add_question(q_num_rebuild, stem, opts, is_tf, correct_is_true, "", correct_fb, incorrect_fb)
                    q_num_rebuild += 1
            
            p_time = parser_end_time - parser_start_time
            a_time = ai_end_time - ai_start_time
            t_time = p_time + a_time
            ai_q_count = len(xml_questions)
            
            report = f"""
================= QA VALIDATION REPORT =================
Document: {course_id} / {document_name}
Parser Questions: {standard_q_count}
AI Validated Questions: {ai_q_count}
Questions Added: {len(additions)}
Questions Corrected: {len(corrections)}
Questions Removed: {len(removals)}
Images Detected: {metadata.get('images_detected', False)} | Preserved: {metadata.get('images_preserved', False)}
Tables Detected: {metadata.get('tables_detected', False)} | Preserved: {metadata.get('tables_preserved', False)}

--- Token & API Metrics ---
Model: {token_usage.get('model', 'N/A')}
Input: {token_usage.get('input', 0)} | Output: {token_usage.get('output', 0)} | Cached: {token_usage.get('cached', 0)} | Total: {token_usage.get('total', 0)}
Finish Reason: {token_usage.get('finish_reason', 'N/A')}
Status: {status_text}

--- Timing ---
Parser Time: {p_time:.2f}s
AI Time: {a_time:.2f}s
Total Time: {t_time:.2f}s
========================================================"""
            logger.info(report)
            if metadata.get("warnings"):
                logger.warning(f"AI QA Warning: {metadata['warnings']}")
        except Exception as e:
            logger.error(f"AI Validation workflow failed: {e}. Falling back to standard parser output.")

    if not xml_questions:
        return 0
        
    if output_xml_path:
        try:
            with open(output_xml_path, 'w', encoding='utf-8') as f:
                f.write(xml_header + '\n'.join(xml_questions) + xml_footer)
            logger.info(f"Successfully created {output_xml_path} with {len(xml_questions)} questions.")
        except Exception as e:
            logger.error(f"Failed to write XML file {output_xml_path}: {e}")
            
    return len(xml_questions)

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

def format_urls_in_soup(soup, link_text: str = "(Disponible aquí)"):
    """
    Finds all URLs (both in <a> tags and plain text) in the given BeautifulSoup object
    and formats them to open in a new tab with the specified link text.
    """
    # First handle URLs that are already inside <a> tags
    for a_tag in soup.find_all("a"):
        # Set target attribute
        a_tag['target'] = "_blank"
        
        # Change the link text
        a_tag.string = link_text
        
        if link_text.lower() == "(disponible aquí)":
            a_tag['style'] = "color: rgb(0, 0, 238); font-size: 13px;"
            a_tag['rel'] = "noopener"
            a_tag['data-asw-orgfontsize'] = "13"
        
        # Clean up preceding text like "Disponible" or colon before the link
        prev_node = a_tag.previous_sibling
        if prev_node and isinstance(prev_node, str):
            # Remove "disponible en:", "disponible:", "disponível em:", "available at:", etc.
            new_text = re.sub(r'(?i)\s*(disponible(s)?|dispon[íi]vel|available)\s*(en|em|at)?\s*:?\s*$', ' ', prev_node)
            if new_text == prev_node:
                # If the specific text is not there, just remove colon if it exists at the end
                new_text = re.sub(r'\s*:\s*$', ' ', prev_node)
            
            if new_text != prev_node:
                prev_node.replace_with(new_text)

    # Next, handle plain text URLs that weren't converted to <a> tags
    pattern = re.compile(r'(?i)(\s*(?:disponible(?:s)?|dispon[íi]vel|available)\s*(?:en|em|at)?\s*:?\s*)?(https?://[^\s<>"]+|www\.[^\s<>"]+)')

    def repl(match):
        url = match.group(2)
        href = url if url.startswith('http') else 'https://' + url
        if link_text.lower() == "(disponible aquí)":
            return f' <a style="color: rgb(0, 0, 238); font-size: 13px;" href="{href}" target="_blank" rel="noopener" data-asw-orgfontsize="13">{link_text}</a>'
        else:
            return f' <a href="{href}" target="_blank" rel="noopener">{link_text}</a>'

    plain_urls_converted = 0
    from bs4 import BeautifulSoup as BS  # Ensure BeautifulSoup is available
    for text_node in soup.find_all(string=True):
        if text_node.parent and text_node.parent.name == 'a':
            continue
        new_html = pattern.sub(repl, text_node)
        if new_html != text_node:
            plain_urls_converted += 1
            new_soup = BS(new_html, 'html.parser')
            text_node.replace_with(new_soup)
            
    if plain_urls_converted > 0:
        logger.info(f"Converted {plain_urls_converted} plain-text URLs to '{link_text}' anchors.")

def format_urls_in_html(html_content: str, link_text: str = "(Disponible aquí)") -> str:
    from bs4 import BeautifulSoup as BS
    if not html_content or not html_content.strip():
        return html_content
    soup = BS(html_content, 'html.parser')
    format_urls_in_soup(soup, link_text)
    return str(soup)

def format_typography_in_html(html_content: str) -> str:
    from bs4 import BeautifulSoup as BS
    if not html_content or not html_content.strip():
        return html_content
    soup = BS(html_content, 'html.parser')
    for tag in soup.find_all(["p", "li"]):
        if tag.find("img"):
            continue
        if not tag.find("span", style=TEXT_SPAN_STYLE):
            new_span = soup.new_tag("span", style=TEXT_SPAN_STYLE)
            for child in list(tag.contents):
                new_span.append(child.extract())
            tag.append(new_span)
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
        "¿Qué vamos a lograr?": "https://unisallevirtual.lasalle.edu.co/multimedia/etiquetas/quevamosalograr.png",
        "¿Cómo lo vamos a lograr?": "https://unisallevirtual.lasalle.edu.co/multimedia/etiquetas/comolovamosalograr.png",
        "¿Cómo lo vamos a evaluar?": "https://unisallevirtual.lasalle.edu.co/multimedia/etiquetas/comolovamosaevaluar.png"
    }
    
    eval_header_p = None
    for p in soup.find_all("p"):
        text = p.get_text(" ", strip=True)
        # Check against heading map
        matched = False
        for target_text, img_url in heading_map.items():
            if target_text in text:
                if target_text == "¿Cómo lo vamos a evaluar?":
                    eval_header_p = p
                p.clear()
                img_tag = soup.new_tag("img", src=img_url, width="60%")
                img_tag["class"] = "img-fluid"
                p.append(img_tag)
                p["data-section"] = target_text
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
            
    # 2.7 Convert local images and apply styles based on section
    current_section = None
    for tag in soup.find_all(True):
        if tag.name == "p" and tag.get("data-section"):
            current_section = tag.get("data-section")
            
        elif tag.name == "img":
            # Skip the actual header images
            if tag.parent and tag.parent.name == "p" and tag.parent.get("data-section"):
                continue
                
            current_style = tag.get("style", "")
            
            if current_section == "¿Cómo lo vamos a lograr?":
                # Remove any existing max-width
                current_style = re.sub(r'max-width:\s*[^;]+;?', '', current_style)
                new_style = current_style + ("; " if current_style and not current_style.endswith(";") else "") + "max-width: 80%; height: auto; border-radius: 8px; display: block; margin: 0 auto;"
                tag["style"] = new_style.strip()
                
                # Center the paragraph containing the image
                if tag.parent and tag.parent.name == "p":
                    parent_style = tag.parent.get("style", "")
                    if "text-align" not in parent_style:
                        tag.parent["style"] = parent_style + ("; " if parent_style and not parent_style.endswith(";") else "") + "text-align: center;"
            else:
                if "max-width" not in current_style:
                    new_style = current_style + ("; " if current_style and not current_style.endswith(";") else "") + "max-width: 100%; height: auto;"
                    tag["style"] = new_style.strip()
                    
            src = tag.get("src")
            if src and not str(src).startswith("data:") and not str(src).startswith("http"):
                filename = os.path.basename(str(src))
                base64_data = get_image_base64(filename, course_id)
                if base64_data:
                    tag["src"] = base64_data
        
    # 3. Format URLs
    format_urls_in_soup(soup, "(Disponible aquí)")
            
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
            table['style'] = "width: 60%; border-collapse: collapse; border: 1px solid #000;"
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
                        td['style'] = "border: 1px solid #000;"
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
                            td['style'] = "border: 1px solid #000;"
                            inner_p = td.find("p")
                            if inner_p: inner_p['align'] = "left"
                        else:
                            td['width'] = "48"
                            td['style'] = "text-align: center; border: 1px solid #000;"
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
                            td['style'] = "border: 1px solid #000;"
                            inner_p = td.find("p")
                            if inner_p:
                                inner_p['align'] = "right"
                                # Replace "La suma total debe dar" with "Total"
                                for t_node in inner_p.find_all(string=True):
                                    if "La suma total" in t_node:
                                        t_node.replace_with("Total")
                        else:
                            td['width'] = "48"
                            td['style'] = "text-align: center; border: 1px solid #000;"
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

    font_style = "font-family: tahoma, arial, helvetica, sans-serif; font-size: small; color: #000000;"

    # Extract Presentación
    for el in soup.find_all(['p', 'h1', 'h2', 'h3']):
        if 'PRESENTACIÓN DEL ESPACIO ACADÉMICO' in el.get_text().upper() or 'PRESENTACION DEL ESPACIO ACADEMICO' in el.get_text().upper():
            nxt = el.find_next_sibling()
            blocks = []
            while nxt and nxt.name not in ['h1', 'h2', 'table']:
                nxt_text = nxt.get_text().upper()
                if 'OPCIÓN METODOLÓGICA' in nxt_text or 'OPCION METODOLOGICA' in nxt_text or 'METODOLOGÍA DE APRENDIZAJE' in nxt_text or 'METODOLOGIA DE APRENDIZAJE' in nxt_text or 'PLAN DE FORMACIÓN' in nxt_text:
                    break
                if hasattr(nxt, 'name') and nxt.name:
                    for tag in [nxt] + nxt.find_all(True):
                        if tag.has_attr('style'):
                            s = tag['style']
                            s = re.sub(r'(?i)font-family\s*:[^;]+;?', '', s)
                            s = re.sub(r'(?i)font-size\s*:[^;]+;?', '', s)
                            tag['style'] = s
                blocks.append(str(nxt))
                nxt = nxt.find_next_sibling()
            presentacion_html = f'<div style="{font_style}">{"".join(blocks)}</div>'
            break

    # Extract Metodología
    for el in soup.find_all(['p', 'h1', 'h2', 'h3']):
        text_upper = el.get_text().upper()
        if 'OPCIÓN METODOLÓGICA DEL ESPACIO ACADÉMICO' in text_upper or 'OPCION METODOLOGICA' in text_upper or 'METODOLOGÍA DE APRENDIZAJE' in text_upper or 'METODOLOGIA DE APRENDIZAJE' in text_upper:
            nxt = el.find_next_sibling()
            blocks = []
            while nxt and nxt.name not in ['h1', 'h2', 'table']:
                if 'PRESENTACIÓN DEL' in nxt.get_text().upper() or 'PLAN DE FORMACIÓN' in nxt.get_text().upper():
                    break
                if hasattr(nxt, 'name') and nxt.name:
                    for tag in [nxt] + nxt.find_all(True):
                        if tag.has_attr('style'):
                            s = tag['style']
                            s = re.sub(r'(?i)font-family\s*:[^;]+;?', '', s)
                            s = re.sub(r'(?i)font-size\s*:[^;]+;?', '', s)
                            tag['style'] = s
                blocks.append(str(nxt))
                nxt = nxt.find_next_sibling()
            metodologia_html = f'<div style="{font_style}">{"".join(blocks)}</div>'
            break

    # Extract course_id from path (e.g. assets\10\raw_docx_extracted.html -> 10)
    course_id = None
    try:
        dirname = os.path.basename(os.path.dirname(extracted_html_path))
        if dirname.isdigit():
            course_id = int(dirname)
    except:
        pass

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
                        raw_src = img['src']
                        # Convert to base64 so it works in Moodle WYSIWYG
                        if raw_src.startswith("data:"):
                            foto = raw_src
                        else:
                            foto = get_image_base64(os.path.basename(raw_src), course_id)
                            if not foto:
                                foto = raw_src

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
                    
        # Remove tabulation from list items
        for list_tag in table_tag.find_all(['ul', 'ol']):
            existing_style = list_tag.get('style', '')
            # Clean up existing padding/margin if any
            existing_style = re.sub(r'(?i)(padding|margin)[^;]+;?', '', existing_style)
            list_tag['style'] = f"padding-left: 0; margin-left: 0; list-style-position: inside; {existing_style}".strip()
            
        for li_tag in table_tag.find_all('li'):
            existing_style = li_tag.get('style', '')
            existing_style = re.sub(r'(?i)(padding|margin)[^;]+;?', '', existing_style)
            li_tag['style'] = f"margin: 0; padding: 0; {existing_style}".strip()
                    
    # Extract Plan de Formación
    tables = soup.find_all('table')
    for t in tables:
        text_upper = t.get_text().upper()
        if 'PLAN DE FORMACIÓN' in text_upper or 'PLAN DE FORMACION' in text_upper:
            # If this table contains a nested table that ALSO matches, skip this outer one
            nested_tables = t.find_all('table')
            has_nested_match = False
            for nt in nested_tables:
                nt_text = nt.get_text().upper()
                if 'PLAN DE FORMACIÓN' in nt_text or 'PLAN DE FORMACION' in nt_text:
                    has_nested_match = True
                    break
            
            if has_nested_match:
                continue

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

