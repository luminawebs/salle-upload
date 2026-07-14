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

def extract_questions_from_html_to_moodle_xml(html_content: str, output_xml_path: str = None, course_id: int = None) -> int:
    """
    Finds questions in HTML (either via <ol> DOM structures or 'Pregunta N' blocks)
    and exports them to a Moodle XML file retaining full HTML.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    xml_questions = []
    
    xml_header = '<?xml version="1.0" encoding="UTF-8"?>\n<quiz>\n'
    xml_footer = '</quiz>\n'
    
    def add_question(q_num, stem_html, options, is_true_false, correct_is_true, feedback_html="", correct_feedback_html="", incorrect_feedback_html=""):
        q_xml = f'<!-- question: {q_num}  -->\n'
        q_type = 'truefalse' if is_true_false else 'multichoice'
        q_xml += f'  <question type="{q_type}">\n'
        q_xml += f'    <name>\n      <text>Pregunta {q_num}</text>\n    </name>\n'
        q_xml += f'    <questiontext format="html">\n      <text><![CDATA[{stem_html}]]></text>\n    </questiontext>\n'
        if feedback_html:
            q_xml += f'    <generalfeedback format="html">\n      <text><![CDATA[{feedback_html}]]></text>\n    </generalfeedback>\n'
        if correct_feedback_html:
            q_xml += f'    <correctfeedback format="html">\n      <text><![CDATA[{correct_feedback_html}]]></text>\n    </correctfeedback>\n'
        if incorrect_feedback_html:
            q_xml += f'    <incorrectfeedback format="html">\n      <text><![CDATA[{incorrect_feedback_html}]]></text>\n    </incorrectfeedback>\n'
        q_xml += '    <defaultgrade>1.0000000</defaultgrade>\n'
        q_xml += '    <penalty>0.3333333</penalty>\n'
        q_xml += '    <hidden>0</hidden>\n'
        
        if is_true_false:
            q_xml += f'    <answer fraction="{"100" if correct_is_true else "0"}" format="moodle_auto_format">\n      <text>true</text>\n    </answer>\n'
            q_xml += f'    <answer fraction="{"0" if correct_is_true else "100"}" format="moodle_auto_format">\n      <text>false</text>\n    </answer>\n'
        else:
            q_xml += '    <single>true</single>\n'
            q_xml += '    <shuffleanswers>true</shuffleanswers>\n'
            q_xml += '    <answernumbering>abc</answernumbering>\n'
            for opt_html, is_correct in options:
                fraction = "100" if is_correct else "0"
                q_xml += f'    <answer fraction="{fraction}" format="html">\n      <text><![CDATA[{opt_html}]]></text>\n    </answer>\n'
                
        q_xml += '  </question>\n'
        xml_questions.append(q_xml)

    q_num = 1
    
    # FORMAT A LOGIC (DOM Based anchored on Respuesta Correcta)
    correct_ps = soup.find_all(lambda tag: tag.name == 'p' and ('Respuesta correcta:' in tag.get_text() or 'Respuestas correctas:' in tag.get_text()))
    for correct_p in correct_ps:
        correct_text = correct_p.get_text(strip=True).replace("Respuesta correcta:", "").replace("Respuestas correctas:", "").strip()
        feedback_html = ""
        feedback_p = correct_p.find_next_sibling('p')
        if feedback_p and ("Retroalimentación:" in feedback_p.get_text() or "Retroalimentación incorrecta:" in feedback_p.get_text()):
            feedback_html = process_image_src(feedback_p.decode_contents().replace("Retroalimentación incorrecta:", "").replace("Retroalimentación:", "").strip(), course_id)
        
        prev_node = correct_p.find_previous_sibling(['ul', 'ol'])
        if not prev_node:
            continue
            
        options_tags = []
        stem_html = ""
        outer_lis = prev_node.find_all('li', recursive=False)
        if outer_lis and outer_lis[-1].find(['ol', 'ul']):
            import copy
            outer_li_clone = copy.copy(outer_lis[-1])
            inner_list = outer_li_clone.find(['ol', 'ul'])
            if inner_list: inner_list.decompose()
            stem_html = process_image_src(outer_li_clone.decode_contents(), course_id)
            inner_lis = outer_lis[-1].find(['ol', 'ul']).find_all('li')
            options_tags = inner_lis
        else:
            options_tags = [li for li in prev_node.find_all('li') if not li.find(['ol', 'ul'])]
            
        if not stem_html:
            stem_p = prev_node.find_previous_sibling('p')
            if stem_p:
                stem_text = stem_p.get_text(strip=True)
                if stem_text.upper() != "PREGUNTAS:" and len(stem_text) > 3 and "respuesta correcta" not in stem_text.lower() and "respuestas correctas" not in stem_text.lower():
                    stem_html = process_image_src(stem_p.decode_contents(), course_id)
            if not stem_html and len(options_tags) > 1:
                stem_html = process_image_src(options_tags[0].decode_contents(), course_id)
                options_tags = options_tags[1:]

        is_true_false = False
        opt_texts = [o.get_text(strip=True) for o in options_tags]
        if len(opt_texts) == 0:
            is_true_false = True
        elif len(opt_texts) == 2:
            opt_lower = [o.lower() for o in opt_texts]
            if any("verdadero" in o or "true" in o for o in opt_lower) and any("falso" in o or "false" in o for o in opt_lower):
                is_true_false = True
                
        if is_true_false or "verdadero" in correct_text.lower() or "falso" in correct_text.lower():
            is_true = "verdadero" in correct_text.lower() or "true" in correct_text.lower()
            add_question(q_num, stem_html, [], True, is_true, feedback_html)
            q_num += 1
        else:
            final_options = []
            for opt_tag, opt_text in zip(options_tags, opt_texts):
                opt_norm = opt_text.lower().strip('. ')
                correct_norm = correct_text.lower().strip('. ')
                is_correct = (opt_norm == correct_norm)
                if not is_correct:
                    clean_opt = re.sub(r'^[a-ea-e][\.\)]\s*', '', opt_norm).strip()
                    clean_correct = re.sub(r'^[a-ea-e][\.\)]\s*', '', correct_norm).strip()
                    is_correct = (clean_opt == clean_correct)
                if not is_correct and len(clean_opt) > 10 and len(clean_correct) > 10:
                    is_correct = (clean_opt in clean_correct or clean_correct in clean_opt)
                final_options.append((process_image_src(opt_tag.decode_contents(), course_id), is_correct))
            
            add_question(q_num, stem_html, final_options, False, False, feedback_html)
            q_num += 1

    # FORMAT B LOGIC (Nested OL/UL with (Respuesta))
    if not xml_questions:
        import copy
        lists = soup.find_all(['ol', 'ul'])
        for lst in lists:
            lis = lst.find_all('li', recursive=False)
            has_respuesta = any("(respuesta" in li.get_text(strip=True).lower() for li in lis)
            is_nested = any(li.find(['ol', 'ul']) for li in lis)
            if has_respuesta and is_nested:
                for li in lis:
                    inner_list = li.find(['ol', 'ul'])
                    if not inner_list: continue
                    
                    li_clone = copy.copy(li)
                    if li_clone.find(['ol', 'ul']):
                        li_clone.find(['ol', 'ul']).decompose()
                    stem_html = process_image_src(li_clone.decode_contents(), course_id)
                    
                    options = []
                    for inner_li in inner_list.find_all('li', recursive=False):
                        opt_html = process_image_src(inner_li.decode_contents(), course_id)
                        is_correct = False
                        if "(respuesta" in inner_li.get_text().lower():
                            is_correct = True
                            opt_html = re.sub(r'(?i)\s*\((respuesta|respuesta correcta)\)', '', opt_html).strip()
                        options.append((opt_html, is_correct))
                    
                    if stem_html and options:
                        add_question(q_num, stem_html, options, False, False)
                        q_num += 1

    # FORMAT C LOGIC (Flat OL/UL or Flat P with marks)
    if not xml_questions:
        def is_correct_option(t):
            return "(respuesta" in t.lower() or "(correct answer)" in t.lower() or bool(re.search(r'(?i)[_\s]*x[_\s]*$', t.strip())) or t.strip().startswith('=')
            
        def clean_option_html(h, t):
            h = re.sub(r'(?i)\s*\((respuesta(?: correcta)?|correct answer)\)', '', h)
            h = re.sub(r'(?i)[_\s]*x[_\s]*$', '', h)
            h = re.sub(r'^\s*=\s*', '', h)
            return h.strip()

        # Check ol/ul first
        lists = soup.find_all(['ol', 'ul'])
        for lst in lists:
            lis = lst.find_all('li', recursive=False)
            has_respuesta = any(is_correct_option(li.get_text(strip=True)) for li in lis)
            if has_respuesta and not any(li.find(['ol', 'ul']) for li in lis):
                current_stem = None
                current_options = []
                current_feedback_html = ""
                current_correct_feedback_html = ""
                current_incorrect_feedback_html = ""
                active_feedback_type = None
                
                for li in lis:
                    text = li.get_text(strip=True)
                    html = process_image_src(li.decode_contents(), course_id)
                    if not text and li.name not in ['img', 'table'] and not li.find(['img', 'table']):
                        continue
                    
                    is_stem = False
                    is_tf = current_options and any('verdadero' in o[1].lower() for o in current_options) and any('falso' in o[1].lower() for o in current_options)
                    
                    is_feedback_header = text.lower().startswith('retroalimentaci') or text.lower().startswith('explicaci')
                    
                    if not is_feedback_header:
                        if text.startswith('¿') or text.endswith('?'):
                            is_stem = True
                        elif text.endswith(':') and not active_feedback_type:
                            is_stem = True
                        elif re.match(r'^\d+\.\s+', text):
                            is_stem = True
                        elif current_stem and (len(current_options) >= 4 or is_tf) and not is_correct_option(text) and not active_feedback_type:
                            is_stem = True
                        
                    if is_stem:
                        if current_stem and current_options:
                            add_question(q_num, current_stem, [(clean_option_html(h, t), is_correct_option(t)) for h, t in current_options], False, False, current_feedback_html, current_correct_feedback_html, current_incorrect_feedback_html)
                            q_num += 1
                        current_stem = html
                        current_options = []
                        current_feedback_html = ""
                        current_correct_feedback_html = ""
                        current_incorrect_feedback_html = ""
                        active_feedback_type = None
                    else:
                        if is_feedback_header:
                            if "correcta" in text.lower() and "incorrecta" not in text.lower(): active_feedback_type = "correct"
                            elif "incorrecta" in text.lower(): active_feedback_type = "incorrect"
                            else: active_feedback_type = "general"
                            
                            clean_html = re.sub(r'(?i)^(?:<[^>]+>)*\s*(?:retroalimentaci[^:]*:|explicaci[^:]*:)\s*(?:</[^>]+>)*', '', html).strip()
                            if clean_html:
                                if active_feedback_type == "correct": current_correct_feedback_html += clean_html
                                elif active_feedback_type == "incorrect": current_incorrect_feedback_html += clean_html
                                else: current_feedback_html += clean_html
                        elif active_feedback_type:
                            if active_feedback_type == "correct": current_correct_feedback_html += ("<br>" if current_correct_feedback_html else "") + html
                            elif active_feedback_type == "incorrect": current_incorrect_feedback_html += ("<br>" if current_incorrect_feedback_html else "") + html
                            else: current_feedback_html += ("<br>" if current_feedback_html else "") + html
                        elif current_stem:
                            if not text:
                                current_stem += "<br>" + html
                            elif not current_options and not re.match(r'^=?[A-Ea-e][\.\)]\s*', text) and not text.lower().startswith('verdadero') and not text.lower().startswith('falso'):
                                current_stem += "<br>" + html
                            else:
                                current_options.append((html, text))
                
                if current_stem and current_options:
                    add_question(q_num, current_stem, [(clean_option_html(h, t), is_correct_option(t)) for h, t in current_options], False, False, current_feedback_html, current_correct_feedback_html, current_incorrect_feedback_html)
                    q_num += 1

        if not xml_questions:
            elements = soup.find_all(['p', 'li', 'div', 'span', 'img', 'table'])
            paragraphs = []
            seen = set()
            for el in elements:
                if any(p in seen for p in el.parents):
                    continue
                seen.add(el)
                paragraphs.append(el)
            has_respuesta = any(is_correct_option(p.get_text(strip=True)) for p in paragraphs)
            if has_respuesta:
                current_stem = None
                current_options = []
                current_feedback_html = ""
                current_correct_feedback_html = ""
                current_incorrect_feedback_html = ""
                active_feedback_type = None
                
                for p in paragraphs:
                    text = p.get_text(strip=True)
                    html = process_image_src(p.decode_contents(), course_id)
                    if not text and p.name not in ['img', 'table'] and not p.find(['img', 'table']):
                        continue
                    
                    if len(text.split()) > 50: continue
                    if "cómo lo vamos a" in text.lower() or "qué vamos a" in text.lower(): continue
                    
                    is_stem = False
                    is_tf = current_options and any('verdadero' in o[1].lower() for o in current_options) and any('falso' in o[1].lower() for o in current_options)
                    
                    is_feedback_header = text.lower().startswith('retroalimentaci') or text.lower().startswith('explicaci')
                    
                    if not is_feedback_header:
                        if text.startswith('¿') or text.endswith('?'):
                            is_stem = True
                        elif text.endswith(':') and not active_feedback_type:
                            is_stem = True
                        elif re.match(r'^(?:Pregunta\s+)?\d+[\.:]?\s*', text, re.IGNORECASE):
                            is_stem = True
                        elif current_stem and (len(current_options) >= 4 or is_tf) and not is_correct_option(text) and not active_feedback_type:
                            is_stem = True
                        
                    if is_stem:
                        if current_stem and current_options:
                            add_question(q_num, current_stem, [(clean_option_html(h, t), is_correct_option(t)) for h, t in current_options], False, False, current_feedback_html, current_correct_feedback_html, current_incorrect_feedback_html)
                            q_num += 1
                        current_stem = html
                        current_options = []
                        current_feedback_html = ""
                        current_correct_feedback_html = ""
                        current_incorrect_feedback_html = ""
                        active_feedback_type = None
                    else:
                        if is_feedback_header:
                            if "correcta" in text.lower() and "incorrecta" not in text.lower(): active_feedback_type = "correct"
                            elif "incorrecta" in text.lower(): active_feedback_type = "incorrect"
                            else: active_feedback_type = "general"
                            
                            clean_html = re.sub(r'(?i)^(?:<[^>]+>)*\s*(?:retroalimentaci[^:]*:|explicaci[^:]*:)\s*(?:</[^>]+>)*', '', html).strip()
                            if clean_html:
                                if active_feedback_type == "correct": current_correct_feedback_html += clean_html
                                elif active_feedback_type == "incorrect": current_incorrect_feedback_html += clean_html
                                else: current_feedback_html += clean_html
                        elif active_feedback_type:
                            if active_feedback_type == "correct": current_correct_feedback_html += ("<br>" if current_correct_feedback_html else "") + html
                            elif active_feedback_type == "incorrect": current_incorrect_feedback_html += ("<br>" if current_incorrect_feedback_html else "") + html
                            else: current_feedback_html += ("<br>" if current_feedback_html else "") + html
                        elif current_stem:
                            if not text:
                                current_stem += "<br>" + html
                            elif not current_options and not re.match(r'^=?[A-Ea-e][\.\)]\s*', text) and not text.lower().startswith('verdadero') and not text.lower().startswith('falso'):
                                current_stem += "<br>" + html
                            else:
                                current_options.append((html, text))
                if current_stem and current_options:
                    add_question(q_num, current_stem, [(clean_option_html(h, t), is_correct_option(t)) for h, t in current_options], False, False, current_feedback_html, current_correct_feedback_html, current_incorrect_feedback_html)
                    q_num += 1

    # FALLBACK LOGIC
    if not xml_questions:
        elements = soup.find_all(['p', 'li', 'div', 'span', 'img', 'table'])
        nodes = []
        seen = set()
        for el in elements:
            if any(p in seen for p in el.parents):
                continue
            seen.add(el)
            nodes.append(el)
            
            
        current_q_num = None
        current_q_label = None
        current_stem_html_parts = []
        current_options = []
        current_feedback_html = ""
        current_correct_feedback_html = ""
        current_incorrect_feedback_html = ""
        active_feedback_type = None
        
        def save_current_fallback_q():
            nonlocal current_q_num, current_stem_html_parts, current_options, current_feedback_html, current_correct_feedback_html, current_incorrect_feedback_html, xml_questions, q_num
            if current_stem_html_parts and current_options:
                stem_html = "<br>".join(current_stem_html_parts)
                try:
                    q_num_padded = int(current_q_num)
                except (ValueError, TypeError):
                    q_num_padded = q_num
                add_question(q_num_padded, stem_html, current_options, False, False, current_feedback_html, current_correct_feedback_html, current_incorrect_feedback_html)
                q_num += 1
            current_stem_html_parts = []
            current_options = []
            current_feedback_html = ""
            current_correct_feedback_html = ""
            current_incorrect_feedback_html = ""
            
        for node in nodes:
            text = node.get_text(strip=True)
            html_str = process_image_src(str(node), course_id)
            
            # If node is empty and not an image/table, skip
            if not text and node.name not in ['img', 'table'] and not node.find(['img', 'table']):
                continue
                
            # Check for new question start
            q_match = re.match(r'(?i)^(Pregunta\s+(\d+)[\.:]?)\s*$', text)
            if q_match:
                save_current_fallback_q()
                current_q_label = q_match.group(1)
                current_q_num = q_match.group(2)
                active_feedback_type = None
                continue
                
            if current_q_num is None:
                continue
                
            # Detect options or feedback
            is_feedback_header = text.lower().startswith("explicaci") or text.lower().startswith("retroalimentaci")
            is_option = re.match(r'^=?[A-Ea-e][\.\)]\s*', text) or text.lower().startswith('verdadero') or text.lower().startswith('falso') or re.search(r'\([xX]\)$', text)
            
            if is_feedback_header:
                if "correcta" in text.lower() and "incorrecta" not in text.lower(): active_feedback_type = "correct"
                elif "incorrecta" in text.lower(): active_feedback_type = "incorrect"
                else: active_feedback_type = "general"
                
                clean_html = re.sub(r'(?i)^(?:<[^>]+>)*\s*(?:retroalimentaci[^:]*:|explicaci[^:]*:)\s*(?:</[^>]+>)*', '', html_str).strip()
                if clean_html:
                    if active_feedback_type == "correct": current_correct_feedback_html += clean_html
                    elif active_feedback_type == "incorrect": current_incorrect_feedback_html += clean_html
                    else: current_feedback_html += clean_html
                continue
                
            if active_feedback_type:
                if active_feedback_type == "correct": current_correct_feedback_html += ("<br>" if current_correct_feedback_html else "") + html_str
                elif active_feedback_type == "incorrect": current_incorrect_feedback_html += ("<br>" if current_incorrect_feedback_html else "") + html_str
                else: current_feedback_html += ("<br>" if current_feedback_html else "") + html_str
                continue
                
            if is_option:
                is_correct = False
                if re.search(r'\([xX]\)$', text):
                    is_correct = True
                    html_str = re.sub(r'\([xX]\)(?=[^>]*(?:<|$))', '', html_str).strip()
                elif text.strip().startswith('='):
                    is_correct = True
                    html_str = re.sub(r'^\s*=\s*(?=[^>]*(?:<|$))', '', html_str).strip()
                elif "(respuesta" in text.lower() or "(correct answer)" in text.lower():
                    is_correct = True
                    html_str = re.sub(r'(?i)\s*\((?:respuesta(?: correcta)?|correct answer)\)', '', html_str).strip()
                
                current_options.append((html_str, is_correct))
            else:
                current_stem_html_parts.append(html_str)
                
        save_current_fallback_q()

    # VALIDATION LOGIC
    if xml_questions:
        valid_q_count = sum(1 for q in xml_questions if 'fraction="100"' in q)
        if valid_q_count < (len(xml_questions) / 2):
            logger.warning(f"Parsed {len(xml_questions)} questions but only {valid_q_count} have correct answers. Discarding and invoking AI.")
            xml_questions = []

    if not xml_questions:
        if "cuestionario" in html_content.lower() or "evaluemos" in html_content.lower() or "pregunta " in html_content.lower():
            logger.info("Parsing found 0 valid questions but keywords indicate a questionnaire. Invoking AI Structurer fallback...")
            try:
                from core.ai_structurer import extract_missing_questions
                ai_result = extract_missing_questions(html_content)
                if ai_result and ai_result.get("extracted_questions"):
                    logger.info(f"AI Structurer successfully extracted {len(ai_result['extracted_questions'])} questions.")
                    logger.warning(f"\n--- AI PRE-LLM PARSER IMPROVEMENT SUGGESTION ---\n{ai_result.get('code_improvement_feedback', '')}\n----------------------------------------------\n")
                    
                    q_num_fallback = 1
                    for q in ai_result["extracted_questions"]:
                        stem = q.get("stem_html", "")
                        opts = []
                        for opt in q.get("options", []):
                            opts.append((opt.get("text_html", ""), opt.get("is_correct", False)))
                        correct_fb = q.get("correct_feedback_html", "")
                        incorrect_fb = q.get("incorrect_feedback_html", "")
                        add_question(q_num_fallback, stem, opts, False, False, "", correct_fb, incorrect_fb)
                        q_num_fallback += 1
            except Exception as e:
                logger.error(f"AI Structurer fallback failed: {e}")

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

def format_urls_in_soup(soup, link_text: str = "(disponible aquí)"):
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

def format_urls_in_html(html_content: str, link_text: str = "(disponible aquí)") -> str:
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
    format_urls_in_soup(soup, "(disponible aquí)")
            
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

