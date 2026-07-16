from bs4 import BeautifulSoup
from .validators import identify_section, is_question_start, is_option, is_feedback
from .utils import clean_question_text, clean_feedback_text, clean_whitespace
from .multichoice import process_multichoice_option
from .truefalse import process_truefalse_option
from .constants import SECTION_DIAGNOSTICO, SECTION_AFIANZAMIENTO, SECTION_EXAMEN

def parse_preguntas_data(raw_html):
    """
    Parses the raw HTML of 'VIR - PREGUNTAS' to extract 
    Examen Diagnóstico, Afianzamiento, and Examen data.
    """
    soup = BeautifulSoup(raw_html, "html.parser")
    
    sections = {
        SECTION_DIAGNOSTICO: [],
        SECTION_AFIANZAMIENTO: [],
        SECTION_EXAMEN: []
    }
    
    current_section = None
    current_question = None
    
    paragraphs = soup.find_all(['p', 'div', 'li'])
    
    for p in paragraphs:
        text = p.get_text(separator=' ', strip=True)
        if not text:
            continue
            
        if not is_question_start(text) and not is_option(text) and not is_feedback(text):
            sec = identify_section(text)
            if sec:
                if current_question and current_section:
                    sections[current_section].append(current_question)
                    current_question = None
                current_section = sec
                continue
            
        if not current_section:
            continue
            
        if is_question_start(text):
            if current_question:
                sections[current_section].append(current_question)
            
            cleaned_text = clean_question_text(text)
            current_question = {
                "pregunta": cleaned_text,
                "opciones": [],
                "respuesta": None,
                "retroalimentacion": None
            }
            continue
            
        if current_question:
            if is_feedback(text):
                current_question["retroalimentacion"] = clean_feedback_text(text)
                continue
                
            if is_option(text):
                if current_section == SECTION_AFIANZAMIENTO:
                    opt_text, is_correct, formatted_ans = process_truefalse_option(text, p)
                else:
                    opt_text, is_correct, formatted_ans = process_multichoice_option(text, p)
                    
                current_question["opciones"].append(opt_text)
                if is_correct:
                    current_question["respuesta"] = formatted_ans
                continue
                
            if not current_question["opciones"]:
                # If we haven't reached options yet, it might be a continuation of the question text
                current_question["pregunta"] += " " + clean_whitespace(text)

    if current_question and current_section:
        sections[current_section].append(current_question)

    return sections
