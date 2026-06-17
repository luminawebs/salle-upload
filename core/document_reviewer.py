import os
import re
import json
import logging
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def review_document(course_id: int, generate_json=True, generate_text=True):
    """
    Reviews the raw_docx_extracted.html for a given course ID to ensure all
    expected structural elements are present. Logs the results in Spanish.
    Optionally saves the results to a JSON and/or text file in the course's assets folder.
    """
    logger.info(f"Iniciando revisión de documento para el curso {course_id}...")
    base_dir = os.path.join(PROJECT_ROOT, "assets", str(course_id))
    raw_html_path = os.path.join(base_dir, "raw_docx_extracted.html")

    report = {
        "curso": course_id,
        "nombre_curso": "Nombre no encontrado",
        "introduccion_general": {"encontrado": False, "detalles": "No se encontró 'Presentación del espacio académico'"},
        "unidades": {}
    }

    if not os.path.exists(raw_html_path):
        msg = f"No se encontró el archivo {raw_html_path}. Ejecuta la extracción DOCX primero."
        logger.error(msg)
        report["error"] = msg
        _save_reports(base_dir, report, generate_json, generate_text)
        return

    with open(raw_html_path, "r", encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, "html.parser")
    
    # 0. Extract Course Name
    for tr in soup.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) >= 2:
            key = tds[0].get_text(strip=True).upper()
            if "NOMBRE DEL ESPACIO ACADÉMICO" in key or "NOMBRE DEL CURSO" in key:
                report["nombre_curso"] = tds[1].get_text(strip=True)
                break

    # 1. Check Introducción General
    intro_found = False
    for h1 in soup.find_all(['h1', 'h2', 'p', 'td']):
        if h1.get_text() and "PRESENTACIÓN DEL ESPACIO ACADÉMICO" in h1.get_text().upper():
            intro_found = True
            break
            
    if intro_found:
        report["introduccion_general"]["encontrado"] = True
        report["introduccion_general"]["detalles"] = "Encontrado"
        logger.info("[ENCONTRADO] Introducción General (Presentación del espacio académico)")
    else:
        logger.warning("[NO ENCONTRADO] Introducción General (Presentación del espacio académico)")

    # 2. Iterate through rows to find Units and their content
    current_unidad = None
    
    # We will track activities per unit to ensure we report on them
    for tr in soup.find_all("tr"):
        text = tr.get_text(strip=True).upper()
        
        # Detect Unit
        match_unidad = None
        for element in tr.find_all(['td', 'p', 'h1', 'h2', 'h3', 'strong', 'b']):
            element_text = element.get_text(strip=True).upper()
            m = re.match(r'^UNIDAD\s*(?:DID\u00c1CTICA)?\s*(\d+)', element_text)
            if m:
                match_unidad = m
                break
                
        if not match_unidad:
            match_unidad = re.match(r'^UNIDAD\s*(?:DID\u00c1CTICA)?\s*(\d+)', text)

        if match_unidad:
            current_unidad = match_unidad.group(1)
            if current_unidad not in report["unidades"]:
                report["unidades"][current_unidad] = {
                    "resumen": {"encontrado": False, "detalles": "No se encontró el resumen"},
                    "preguntas_orientadoras": {"encontrado": False, "detalles": "No se encontraron preguntas orientadoras", "cantidad": 0},
                    "actividades": {},
                    "material_referencia": {"encontrado": False, "detalles": "No se encontró material de referencia o lecturas complementarias"}
                }
                logger.info(f"[ENCONTRADO] Unidad Didáctica {current_unidad}")
            continue

        if current_unidad:
            tds = tr.find_all("td")
            if len(tds) >= 1:
                td1_text = tds[0].get_text(strip=True).upper()
                
                # Resumen
                if td1_text.startswith("RESUMEN"):
                    report["unidades"][current_unidad]["resumen"]["encontrado"] = True
                    report["unidades"][current_unidad]["resumen"]["detalles"] = "Encontrado"
                    
                # Preguntas orientadoras
                elif "PREGUNTAS ORIENTADORAS" in td1_text:
                    report["unidades"][current_unidad]["preguntas_orientadoras"]["encontrado"] = True
                    report["unidades"][current_unidad]["preguntas_orientadoras"]["detalles"] = "Encontrado"
                    
                    target_td = tds[1] if len(tds) > 1 else tds[0]
                    num_questions = len(target_td.find_all("li"))
                    if num_questions == 0:
                        num_questions = target_td.get_text().count("?")
                    report["unidades"][current_unidad]["preguntas_orientadoras"]["cantidad"] = num_questions
            
            # Actividades
            match_actividad = re.search(r'ACTIVIDAD\s+(\d+)\s*[:\.]', text)
            if match_actividad:
                act_num = match_actividad.group(1)
                current_actividad = act_num
                if act_num not in report["unidades"][current_unidad]["actividades"]:
                    report["unidades"][current_unidad]["actividades"][act_num] = {
                        "tipo": "Desconocido",
                        "cantidad_preguntas": 0
                    }
            
            # Count preguntas if inside an activity
            if 'current_actividad' in locals() and current_actividad and current_actividad in report["unidades"][current_unidad]["actividades"]:
                preguntas = re.findall(r'PREGUNTA\s+(\d+)[:\.]?', text)
                if preguntas:
                    max_preg = max(int(p) for p in preguntas)
                    current_count = report["unidades"][current_unidad]["actividades"][current_actividad]["cantidad_preguntas"]
                    report["unidades"][current_unidad]["actividades"][current_actividad]["cantidad_preguntas"] = max(current_count, max_preg)

            # Detectar tipo de actividad
            if "HERRAMIENTA" in text and "PLATAFORMA VIRTUAL" in text:
                if 'current_actividad' in locals() and current_actividad and current_actividad in report["unidades"][current_unidad]["actividades"]:
                    raw_text = tr.get_text().upper()
                    tipo_actividad = "Desconocido"
                    if re.search(r'FORO[_\s]*X', raw_text):
                        tipo_actividad = "Foro"
                    elif re.search(r'TAREA[_\s]*X', raw_text):
                        tipo_actividad = "Tarea"
                    elif re.search(r'CUESTIONARIO[_\s]*X', raw_text):
                        tipo_actividad = "Cuestionario"
                    elif re.search(r'NO SABE[_\s]*X', raw_text):
                        tipo_actividad = "No sabe"
                    elif re.search(r'OTRA[_\s¿A-Z\?]*X', raw_text):
                        tipo_actividad = "Otra"
                    
                    report["unidades"][current_unidad]["actividades"][current_actividad]["tipo"] = tipo_actividad

            # Material de Referencia / Lecturas Complementarias
            if "LECTURAS COMPLEMENTARIAS" in text or "MATERIAL DE REFERENCIA" in text or "LECTURAS DE REFERENCIA" in text:
                report["unidades"][current_unidad]["material_referencia"]["encontrado"] = True
                report["unidades"][current_unidad]["material_referencia"]["detalles"] = "Encontrado"

    # Log results for units
    if not report["unidades"]:
        logger.warning("[NO ENCONTRADO] Ninguna Unidad Didáctica se encontró en el documento.")
    else:
        for u_num, u_data in report["unidades"].items():
            # Log Resumen
            if u_data["resumen"]["encontrado"]:
                logger.info(f"[ENCONTRADO] Resumen para la Unidad {u_num}")
            else:
                logger.warning(f"[NO ENCONTRADO] Resumen para la Unidad {u_num}")
                
            # Log Preguntas
            if u_data["preguntas_orientadoras"]["encontrado"]:
                logger.info(f"[ENCONTRADO] Preguntas orientadoras para la Unidad {u_num} ({u_data['preguntas_orientadoras']['cantidad']})")
            else:
                logger.warning(f"[NO ENCONTRADO] Preguntas orientadoras para la Unidad {u_num}")
                
            # Log Actividades
            if u_data["actividades"]:
                for act_num, act_data in u_data["actividades"].items():
                    logger.info(f"[ENCONTRADO] Actividad {act_num} ({act_data['tipo']}) en la Unidad {u_num}")
            else:
                logger.warning(f"[NO ENCONTRADO] Ninguna actividad en la Unidad {u_num}")
                
            # Log Material
            if u_data["material_referencia"]["encontrado"]:
                logger.info(f"[ENCONTRADO] Material de referencia para la Unidad {u_num}")
            else:
                logger.warning(f"[NO ENCONTRADO] Material de referencia para la Unidad {u_num}")

    logger.info("✓ Revisión de documento completada.")
    _save_reports(base_dir, report, generate_json, generate_text)
    return report

def _save_reports(base_dir, report, generate_json, generate_text):
    if generate_json:
        json_path = os.path.join(base_dir, "reporte_revision.json")
        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=4, ensure_ascii=False)
            logger.info(f"Reporte JSON guardado en: {json_path}")
        except Exception as e:
            logger.error(f"Error al guardar reporte JSON: {e}")

    if generate_text:
        text_path = os.path.join(base_dir, "reporte_revision.txt")
        try:
            with open(text_path, "w", encoding="utf-8") as f:
                f.write(f"REPORTE DE REVISIÓN DE DOCUMENTO - CURSO {report.get('curso')}\n")
                f.write("="*60 + "\n\n")
                
                if "error" in report:
                    f.write(f"ERROR: {report['error']}\n")
                    return
                
                # Introducción
                intro = report.get("introduccion_general", {})
                if intro.get("encontrado"):
                    f.write("[✓] Introducción General (Presentación del espacio académico) encontrada.\n")
                else:
                    f.write("[X] Introducción General (Presentación del espacio académico) NO encontrada.\n")
                    
                f.write("\n")
                
                unidades = report.get("unidades", {})
                if not unidades:
                    f.write("[X] No se encontraron Unidades Didácticas.\n")
                else:
                    for u_num, u_data in unidades.items():
                        f.write(f"--- UNIDAD {u_num} ---\n")
                        
                        if u_data["resumen"]["encontrado"]:
                            f.write("  [✓] Resumen encontrado.\n")
                        else:
                            f.write("  [X] Resumen NO encontrado.\n")
                            
                        if u_data["preguntas_orientadoras"]["encontrado"]:
                            f.write("  [✓] Preguntas orientadoras encontradas.\n")
                        else:
                            f.write("  [X] Preguntas orientadoras NO encontradas.\n")
                            
                        if u_data["actividades"]:
                            acts = ", ".join([f"{num} ({data['tipo']})" for num, data in u_data["actividades"].items()])
                            f.write(f"  [✓] Actividades encontradas: {acts}\n")
                        else:
                            f.write("  [X] Actividades NO encontradas.\n")
                            
                        if u_data["material_referencia"]["encontrado"]:
                            f.write("  [✓] Material de referencia / Lecturas complementarias encontrado.\n")
                        else:
                            f.write("  [X] Material de referencia / Lecturas complementarias NO encontrado.\n")
                            
                        f.write("\n")
                        
            logger.info(f"Reporte de texto guardado en: {text_path}")
        except Exception as e:
            logger.error(f"Error al guardar reporte de texto: {e}")
