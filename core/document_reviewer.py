import os
import re
import json
import logging
import shutil
from bs4 import BeautifulSoup
from core.document_headings import bare_unit_number, is_intro_heading

logger = logging.getLogger(__name__)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def review_document(course_id: int, generate_json=True, generate_text=True, cleanup_fragments=True):
    """
    Reviews the raw_docx_extracted.html for a given course ID to ensure all
    expected structural elements are present. Logs the results in Spanish.
    Optionally saves the results to a JSON and/or text file in the course's assets folder.

    cleanup_fragments: when True (default, unchanged behavior), the per-item
    HTML/XML fragments written by run_docx_splitting_workflow (actividades/,
    material/, introduccion/) are deleted once the report is built. Pass
    False to keep them on disk so a UI can show exactly how each item was
    parsed (e.g. workspace/<course_id>/actividades/actividad3.html).
    """
    logger.info(f"Iniciando revisión de documento para el curso {course_id}...")
    base_dir = os.path.join(PROJECT_ROOT, "workspace", str(course_id))
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

    # Run the *real* splitter used by the actual automation pipeline, and
    # keep its returned manifest as the single source of truth for which
    # activities exist and what type each is. This report used to detect
    # units/activities/types itself with a second, separate implementation —
    # the two could (and did) drift apart, e.g. a body paragraph mentioning
    # a previous activity in prose could hijack this report's detection
    # while the real splitter, scoped correctly per activity, stayed right.
    activity_manifest = {}
    try:
        from core.data_parser import run_docx_splitting_workflow
        activity_manifest = run_docx_splitting_workflow(course_id) or {}
    except Exception as e:
        logger.error(f"Error executing DOCX splitting workflow: {e}")

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
        if h1.get_text() and is_intro_heading(h1.get_text().upper()):
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
        
        # Detect Unit: "UNIDAD DIDÁCTICA N" first (matching is anchored to the
        # element/row text here); a bare "UNIDAD N." heading is handled just
        # below via the shared rule in core/document_headings.py.
        match_unidad = None
        for element in tr.find_all(['td', 'p', 'h1', 'h2', 'h3', 'strong', 'b']):
            element_text = element.get_text(strip=True).upper()
            m = re.match(r'^UNIDAD\s*DID\u00c1CTICA\s*(\d+)', element_text)
            if m:
                match_unidad = m
                break

        if not match_unidad:
            match_unidad = re.match(r'^UNIDAD\s*DID\u00c1CTICA\s*(\d+)', text)

        unit_key = match_unidad.group(1) if match_unidad else None
        if unit_key is None:
            # Bare "UNIDAD N." heading alone in its row, the same rule the
            # splitter and the Moodle structure parser use (see
            # core/document_headings.py), so this report and the real pipeline
            # agree on what a unit is. Summary-table rows have several cells
            # and are never accepted here.
            bare = bare_unit_number(text, tr)
            if bare is not None:
                unit_key = str(bare)

        if unit_key is not None:
            current_unidad = unit_key
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
            
            # Note: activities and their "tipo" are no longer detected here.
            # They're folded in below from activity_manifest — the exact
            # structure the real splitter (core/data_parser.py) produced —
            # instead of a second, independent detection pass that could
            # disagree with it.

            # Material de Referencia / Lecturas Complementarias
            if "LECTURAS COMPLEMENTARIAS" in text or "MATERIAL DE REFERENCIA" in text or "LECTURAS DE REFERENCIA" in text:
                report["unidades"][current_unidad]["material_referencia"]["encontrado"] = True
                report["unidades"][current_unidad]["material_referencia"]["detalles"] = "Encontrado"

    # Fold in the activities exactly as the real splitter detected them, so
    # this report can never show a different activity count/number/type
    # than what the actual automation pipeline will act on.
    for unit_key, unit_activities in activity_manifest.items():
        if unit_key not in report["unidades"]:
            # The splitter found a "UNIDAD DIDÁCTICA n" this report's own
            # (lighter) heading scan missed — surface its activities anyway
            # instead of silently dropping them.
            report["unidades"][unit_key] = {
                "resumen": {"encontrado": False, "detalles": "No se encontró el resumen"},
                "preguntas_orientadoras": {"encontrado": False, "detalles": "No se encontraron preguntas orientadoras", "cantidad": 0},
                "actividades": {},
                "material_referencia": {"encontrado": False, "detalles": "No se encontró material de referencia o lecturas complementarias"}
            }
        for act_num, act_info in unit_activities.items():
            report["unidades"][unit_key]["actividades"][act_num] = {
                "tipo": act_info["tipo"],
                "cantidad_preguntas": 0
            }

    # Clean up temporary split folders (unless the caller wants to keep them
    # around, e.g. to let a UI show exactly how each item was parsed)
    if cleanup_fragments:
        for folder in ["actividades", "material", "introduccion"]:
            folder_path = os.path.join(base_dir, folder)
            if os.path.exists(folder_path):
                try:
                    shutil.rmtree(folder_path)
                except Exception as e:
                    logger.error(f"Error al eliminar la carpeta {folder_path}: {e}")

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
