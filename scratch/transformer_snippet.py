import os
import re
import base64
import logging
from bs4 import BeautifulSoup
from core.question_types import MultichoiceQuestion, ClozeQuestion, DragDropQuestion

logger = logging.getLogger(__name__)

TEXT_SPAN_STYLE = "font-family: tahoma, arial, helvetica, sans-serif; font-size: small; color: #000000;"
RUBRIC_HEADER_STYLE = "background-color: #e7b917;"

def get_image_base64(image_filename: str, course_id: int = None) -> str:
    image_path = None
    
    # 1. First, check if the image is in the specific course's img folder
    if course_id:
        course_img = os.path.join("workspace", str(course_id), "imgs", image_filename)
        if os.path.exists(course_img):
            image_path = course_img

    if not image_path:
        # 2. If not, check if it's a shared global asset
        # Try shared workspace
        shared_img = os.path.join("workspace", "shared", image_filename)
        if os.path.exists(shared_img):
            image_path = shared_img
            
    if not image_path:
        # 3. Fallback: check the example course folder (for testing/development)
        example_img = os.path.join("workspace", "example_course", image_filename)
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
        if current_q and current_q['stem_html']:
            questions.append(current_q)
            
    def create_empty_q():
        return {
            'stem_html': [],
            'options': [],
            'feedback': {'general': [], 'correct': [], 'incorrect': []},
            'base_list_level': 0,
            'active_fb_type': 'general',
            'q_type': 'multichoice'
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
            
        # 2a. Check if Type header
        if re.match(r'(?i)^Tipo:\s*(.*)', text):
            type_val = re.match(r'(?i)^Tipo:\s*(.*)', text).group(1).lower().strip()
            if current_q and state in ['SEARCHING', 'STEM']:
                if 'completar' in type_val or 'cloze' in type_val:
                    current_q['q_type'] = 'cloze'
                elif 'arrastrar' in type_val or 'drag' in type_val:
                    current_q['q_type'] = 'drag_drop'
                elif 'verdadero' in type_val:
                    current_q['q_type'] = 'truefalse'
            continue

        # 2b. Check if Feedback
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
            
        # 2c. Check if Option
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
                clean_html_opt = re.sub(r'(>|^)\s*=\s*', r'\1', clean_html_opt, count=1).strip()
            elif "(respuesta" in text.lower() or "(correct answer)" in text.lower():
                is_correct = True
                clean_html_opt = re.sub(r'(?i)\s*\((?:respuesta(?: correcta)?|correct answer)\)', '', clean_html_opt).strip()
                
            if state in ['SEARCHING', 'STEM']:
                state = 'OPTIONS'
            current_q['options'].append({'html': clean_html_opt, 'is_correct': is_correct})
            continue

        # 2d. Check if Question Start
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
            
        # 2e. Append to current state
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

    q_num = 1
    for q in questions:
        stem_html = "<br>".join(q['stem_html'])
        opts = []
        is_true_false = False
        correct_is_true = False
        
        for o in q['options']:
            opts.append((o['html'], o['is_correct']))
            
        # Detect true/false heuristically if not set explicitly
        if q['q_type'] == 'multichoice':
            opt_texts = [BeautifulSoup(o[0], 'html.parser').get_text(strip=True).lower() for o in opts]
            if len(opt_texts) == 2:
                if any(x in txt for txt in opt_texts for x in ['verdadero', 'true']) and any(x in txt for txt in opt_texts for x in ['falso', 'false']):
                    is_true_false = True
                    q['q_type'] = 'truefalse'
                    for o_html, is_corr in opts:
                        if is_corr and any(x in o_html.lower() for x in ['verdadero', 'true']):
                            correct_is_true = True
                            
        if q['q_type'] == 'truefalse':
            is_true_false = True
            
        fb_gen = "<br>".join(q['feedback']['general'])
        fb_corr = "<br>".join(q['feedback']['correct'])
        fb_inc = "<br>".join(q['feedback']['incorrect'])
        
        if q['q_type'] in ['multichoice', 'truefalse']:
            q_handler = MultichoiceQuestion(
                q_num, stem_html, opts, fb_gen, fb_corr, fb_inc, course_id, document_name,
                is_true_false=is_true_false, correct_is_true=correct_is_true
            )
        elif q['q_type'] == 'cloze':
            q_handler = ClozeQuestion(
                q_num, stem_html, opts, fb_gen, fb_corr, fb_inc, course_id, document_name
            )
        elif q['q_type'] == 'drag_drop':
            q_handler = DragDropQuestion(
                q_num, stem_html, opts, fb_gen, fb_corr, fb_inc, course_id, document_name
            )
        else:
            q_handler = MultichoiceQuestion(q_num, stem_html, opts, fb_gen, fb_corr, fb_inc, course_id, document_name)
            
        xml_questions.append(q_handler.to_moodle_xml())
        
        # Build structured output for AI QA
        q_dict = {
            "stem_html": stem_html,
            "options": [],
            "correct_feedback_html": fb_corr or fb_gen,
            "incorrect_feedback_html": fb_inc or fb_gen
        }
        
        if q['q_type'] == 'truefalse':
            q_dict["options"].append({"text_html": "true", "is_correct": correct_is_true})
            q_dict["options"].append({"text_html": "false", "is_correct": not correct_is_true})
        else:
            for opt_html, is_correct in opts:
                q_dict["options"].append({"text_html": opt_html, "is_correct": is_correct})
                
        structured_questions.append(q_dict)
        q_num += 1

    # --- 4. VALIDATION LOGIC (AI QA Layer) ---
