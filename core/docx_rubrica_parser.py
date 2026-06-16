import re
import logging
from bs4 import BeautifulSoup
import os

logger = logging.getLogger(__name__)

LEVEL_DESCRIPTIONS = [
    "Lo evidencia plenamente",
    "Lo evidencia y requiere mejoras mínimas",
    "Lo evidencia parcialmente",
    "Lo evidencia de forma mínima",
    "No lo evidencia"
]

def calculate_scores(base_score_str: str) -> list[str]:
    """
    Calculates the 5 level scores based on the initial base score.
    Follows specific rules for base 2 and base 1, otherwise proportional (100%, 75%, 50%, 25%, 0%).
    """
    try:
        base_score = float(base_score_str.replace(',', '.'))
    except ValueError:
        logger.warning(f"Could not parse base score '{base_score_str}', defaulting to 0.")
        return ["0", "0", "0", "0", "0"]

    if abs(base_score - 2.0) < 0.01:
        return ["2", "1.5", "1", "0.5", "0"]
    elif abs(base_score - 1.0) < 0.01:
        return ["1", "0.8", "0.6", "0.3", "0"]
    else:
        # Proportional scaling (100%, 75%, 50%, 25%, 0%)
        return [
            f"{base_score:g}",
            f"{round(base_score * 0.75, 2):g}",
            f"{round(base_score * 0.50, 2):g}",
            f"{round(base_score * 0.25, 2):g}",
            "0"
        ]

def parse_rubricas_from_docx(course_id: int) -> dict:
    """
    Parses the raw_docx_extracted.html file and extracts grading rubrics
    ("Criterios de desempeño") for each Actividad.
    
    Returns a dictionary mapping Actividad number (int) to a list of criteria dictionaries.
    {
        1: [
            {
                "name": "Criterio 1...",
                "levels": ["Lo evidencia...", ...],
                "scores": ["2", "1.5", "1", "0.5", "0"]
            },
            ...
        ],
        ...
    }
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    html_path = os.path.join(base_dir, "assets", str(course_id), "raw_docx_extracted.html")
    
    if not os.path.exists(html_path):
        logger.warning(f"No raw_docx_extracted.html found at {html_path}. Cannot parse rubrics.")
        return {}

    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, "html.parser")
    rubricas = {}

    for tr in soup.find_all("tr"):
        tr_text = tr.get_text(strip=True).upper()
        actividad_match = re.search(r'ACTIVIDAD\s*(\d+)', tr_text)
        if actividad_match and "ACTIVIDADES DE APRENDIZAJE" not in tr_text:
            act_num = int(actividad_match.group(1))
            
            # Find the next table that contains "Criterios de desempeño"
            next_criterios_table = None
            curr = tr
            while curr:
                text = curr.get_text()
                if 'Criterios de desempeño' in text and 'Puntos' in text:
                    table = curr.find('table')
                    if not table and curr.parent.name == 'table':
                        table = curr.find_next('table')
                    if table and 'Criterios de desempeño' in table.get_text():
                        next_criterios_table = table
                        break
                curr = curr.find_next_sibling('tr')
                if curr and re.search(r'ACTIVIDAD\s*\d+', curr.get_text().upper()) and "ACTIVIDADES DE APRENDIZAJE" not in curr.get_text().upper():
                    break
                    
            if next_criterios_table:
                criteria_list = []
                rows = next_criterios_table.find_all('tr', recursive=False)
                if not rows and next_criterios_table.tbody:
                    rows = next_criterios_table.tbody.find_all('tr', recursive=False)
                
                for i, row in enumerate(rows):
                    if i == 0:
                        continue # Skip header row
                    
                    cols = row.find_all(['th', 'td'], recursive=False)
                    if len(cols) >= 2:
                        criterio_text = cols[0].get_text(strip=True)
                        puntos_text = cols[1].get_text(strip=True)
                        
                        if "Total" in criterio_text or "suma total" in criterio_text.lower() or not criterio_text:
                            continue
                        
                        scores = calculate_scores(puntos_text)
                        criteria_list.append({
                            "name": criterio_text,
                            "levels": LEVEL_DESCRIPTIONS,
                            "scores": scores
                        })
                
                if criteria_list:
                    rubricas[act_num] = criteria_list
                    logger.info(f"Parsed rubric for Actividad {act_num} with {len(criteria_list)} criteria.")

    return rubricas
