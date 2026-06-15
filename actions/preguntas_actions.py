import logging
import os
import json
import time
from bs4 import BeautifulSoup
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import Config
from actions.moodle_actions import navigate_to_course

logger = logging.getLogger(__name__)

def parse_preguntas_data(raw_html):
    """
    Parses the raw HTML of 'VIR - PREGUNTAS' to extract 
    Examen Diagnóstico, Afianzamiento, and Examen data.
    """
    soup = BeautifulSoup(raw_html, "html.parser")
    
    sections = {
        "diagnostico": [],
        "afianzamiento": [],
        "examen": []
    }
    
    current_section = None
    current_question = None
    
    def identify_section(text):
        if len(text) > 100:
            return None
        t = text.upper()
        if "DIAGNÓSTICO" in t or "DIAGNOSTICO" in t:
            return "diagnostico"
        if "AFIANZAMIENTO" in t:
            return "afianzamiento"
        if "EXÁMEN" in t or "EXAMEN" in t:
            if "DIAGN" not in t:
                return "examen"
        return None

    def is_question_start(text):
        return re.match(r'^\s*\d+[\.\)]\s*', text) is not None

    def is_option(text):
        if re.match(r'^\s*[A-Ea-e][\)\.]\s*', text):
            return True
        t = text.strip().lower()
        if t in ["verdadero", "falso"]:
            return True
        return False

    def is_feedback(text):
        return "RETROALIMENTACI" in text.upper()

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
            
            # Remove line breaks and numeration from question
            cleaned_text = re.sub(r'\s+', ' ', text)
            cleaned_text = re.sub(r'^\s*\d+[\.\)]\s*', '', cleaned_text)
            current_question = {
                "pregunta": cleaned_text,
                "opciones": [],
                "respuesta": None,
                "retroalimentacion": None
            }
            continue
            
        if current_question:
            if is_feedback(text):
                feed = re.sub(r'^\s*retroalimentaci[oó]n\s*:\s*', '', text, flags=re.IGNORECASE)
                current_question["retroalimentacion"] = re.sub(r'\s+', ' ', feed)
                continue
                
            if is_option(text):
                opt_text = re.sub(r'\s+', ' ', text)
                is_correct = False
                bold_tag = p.find(['strong', 'b'])
                if bold_tag and bold_tag.get_text(strip=True):
                    bold_text = bold_tag.get_text(strip=True)
                    if len(bold_text) >= len(text) * 0.5:
                        is_correct = True
                        
                current_question["opciones"].append(opt_text)
                if is_correct:
                    val = opt_text.strip()
                    if current_section == "afianzamiento":
                        current_question["respuesta"] = "true" if "VERDADERO" in val.upper() else "false"
                    else:
                        current_question["respuesta"] = opt_text
                continue
                
            if not current_question["opciones"]:
                current_question["pregunta"] += " " + re.sub(r'\s+', ' ', text)

    if current_question and current_section:
        sections[current_section].append(current_question)

    return sections


def generate_afianzamiento_html(parsed_data, template_path, output_path):
    """
    Generates the Afianzamiento HTML file using the afianzamiento template.
    """
    with open(template_path, 'r', encoding='utf-8') as f:
        template_html = f.read()
        
    soup = BeautifulSoup(template_html, "html.parser")
    container = soup.find(id="virtual-questions-container")
    
    if container:
        container.clear()
        
        afianzamiento_questions = parsed_data.get("afianzamiento", [])
        for i, q in enumerate(afianzamiento_questions):
            question_div = soup.new_tag("div", attrs={"class": "virtual-af-question"})
            question_div["data-answer"] = q.get("respuesta", "true")
            question_div["data-feedback"] = q.get("retroalimentacion") or "Respuesta registrada."
            
            p_tag = soup.new_tag("p")
            p_tag.string = q.get("pregunta", "")
            question_div.append(p_tag)
            
            # Verdadero button
            label_v = soup.new_tag("label", attrs={"class": "v-af-button"})
            label_v.string = "Verdadero"
            input_v = soup.new_tag("input", attrs={"type": "radio", "name": f"question{i}", "value": "true"})
            label_v.append(input_v)
            question_div.append(label_v)
            
            # Falso button
            label_f = soup.new_tag("label", attrs={"class": "v-af-button"})
            label_f.string = "Falso"
            input_f = soup.new_tag("input", attrs={"type": "radio", "name": f"question{i}", "value": "false"})
            label_f.append(input_f)
            question_div.append(label_f)
            
            container.append(question_div)
            
    final_html = soup.prettify(formatter="minimal")
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(final_html)

from actions.moodle_actions import navigate_to_course, upload_moodle_wysiwyg

def run_preguntas_workflow(driver, course_id, wait_time=10):
    """
    Iterates through weeks in pairs (1 and 2, 3 and 4, etc.), reads the local Afianzamiento HTML,
    parses it, and assigns the full parsed content to the even week of each pair (2, 4, 6, 8).
    Updates contenidos.json only for those even weeks, generates the corresponding afianzamiento
    HTML files, and uploads them to Moodle.
    """
    logger.info(f"Starting PREGUNTAS export workflow for course {course_id}...")
    
    json_path = os.path.join("assets", str(course_id), "contenidos.json")
    if not os.path.exists(json_path):
        logger.warning(f"Mapping file {json_path} not found. Skipping preguntas export.")
        return False
        
    with open(json_path, "r", encoding="utf-8") as f:
        try:
            contenidos_data = json.load(f)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON in {json_path}")
            return False
            
    template_path = os.path.join("assets", "templates", "afianzamiento.html")
    if not os.path.exists(template_path):
        logger.error(f"Afianzamiento template not found at {template_path}. Cannot generate HTML files.")
        return False
        
    updated = False
    target_even_weeks = []
    
    for pair in [(1, 2), (3, 4), (5, 6), (7, 8)]:
        w1, w2 = pair
        target_week = w2
        target_week_name = f"Semana {target_week}"
        
        file_path = os.path.join("assets", str(course_id), "afianzamiento", f"Actividad Afianzamiento_S{w1} y {w2}.html")
        if not os.path.exists(file_path):
            logger.warning(f"Local file {file_path} not found. Skipping target {target_week_name}.")
            continue
            
        with open(file_path, "r", encoding="utf-8") as f:
            raw_html = f.read()
            
        parsed_data = parse_preguntas_data(raw_html)
        
        if target_week_name in contenidos_data:
            contenidos_data[target_week_name]["preguntas"] = parsed_data
            updated = True
            output_path_target = os.path.join("assets", str(course_id), "afianzamiento", f"s{target_week}_afianzamiento.html")
            generate_afianzamiento_html(parsed_data, template_path, output_path_target)
            target_even_weeks.append(target_week)
            logger.info(f"Generated Afianzamiento HTML for {target_week_name} at {output_path_target}")
        else:
            logger.warning(f"{target_week_name} not found in contenidos.json. Skipping assignment for pair S{w1} y {w2}.")

    if updated:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(contenidos_data, f, ensure_ascii=False, indent=4)
        logger.info(f"Successfully updated {json_path} with preguntas content.")
        
        logger.info("Starting upload of generated Afianzamiento HTML files to Moodle...")
        for i in target_even_weeks:
            output_filename = f"s{i}_afianzamiento.html"
            output_path = os.path.join("assets", str(course_id), "afianzamiento", output_filename)
            
            if os.path.exists(output_path):
                with open(output_path, "r", encoding="utf-8") as f:
                    html_to_upload = f.read()
                
                week_name = f"Semana {i}"
                afianzamiento_resource_name = f"S{i} | Afianzamiento"
                success = upload_moodle_wysiwyg(driver, course_id, week_name, afianzamiento_resource_name, html_to_upload, wait_time)
                if success:
                    logger.info(f"Successfully uploaded {output_filename} to {week_name}")
                else:
                    logger.error(f"Failed to upload {output_filename} to {week_name} (Resource might not exist)")
            else:
                logger.debug(f"File {output_path} not found, skipping upload for Week {i}.")
    else:
        logger.info("No preguntas content was parsed or updated.")
        
    return True
