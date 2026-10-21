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
    html_path = os.path.join(base_dir, "workspace", str(course_id), "raw_docx_extracted.html")
    
    if not os.path.exists(html_path):
        logger.warning(f"No raw_docx_extracted.html found at {html_path}. Cannot parse rubrics.")
        return {}

    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    return parse_rubricas_from_html(html)


def parse_rubricas_from_html(html: str) -> dict:
    """Same as parse_rubricas_from_docx, for an HTML string already in memory."""
    soup = BeautifulSoup(html, "html.parser")
    rubricas = {}

    for tr in soup.find_all("tr"):
        tr_text = tr.get_text(strip=True).upper()
        actividad_match = re.search(r'^ACTIVIDAD\s*(\d+)', tr_text)
        if actividad_match and "ACTIVIDADES DE APRENDIZAJE" not in tr_text:
            act_num = int(actividad_match.group(1))
            
            # Every "Criterios de desempeño" table of this activity (up to the
            # next ACTIVIDAD row); _pick_rubric_table chooses the grading one.
            candidates = []
            curr = tr
            while curr:
                text = curr.get_text()
                if 'Criterios de desempe' in text and 'Puntos' in text:
                    tables = [t for t in curr.find_all('table') if 'Criterios de desempe' in t.get_text()]
                    if not tables and curr.parent.name == 'table':
                        following = curr.find_next('table')
                        tables = [following] if following and 'Criterios de desempe' in following.get_text() else []
                    for table in _innermost(tables):
                        if not any(table is c for c in candidates):
                            candidates.append(table)
                curr = curr.find_next_sibling('tr')
                if curr:
                    text_upper = curr.get_text().upper()
                    if 'CRITERIOS DE DESEMPE' not in text_upper and re.search(r'^ACTIVIDAD\s*\d+', text_upper) and "ACTIVIDADES DE APRENDIZAJE" not in text_upper:
                        break
            next_criterios_table = _pick_rubric_table(candidates)

            if next_criterios_table:
                criteria_list = criteria_from_table(next_criterios_table)
                if criteria_list:
                    rubricas[act_num] = criteria_list
                    logger.info(f"Parsed rubric for Actividad {act_num} with {len(criteria_list)} criteria.")

    return rubricas


# The heading of the section with the activity's grading rubric. Some activities
# have another rubric table before it — e.g. under "Fase 2: Coevaluación", the
# one students share in the forum to evaluate another group — and the first
# table used to be uploaded as the activity's rubric.
_EVALUATION_HEADING_RE = re.compile(r"c[oó]mo\s+lo\s+vamos\s+a\s+evaluar", re.IGNORECASE)
_SECTION_MARKER_RE = re.compile(r"c[oó]mo\s+lo\s+vamos\s+a\s+evaluar|coevaluaci|autoevaluaci|heteroevaluaci|fase\s+\d", re.IGNORECASE)


def _innermost(tables) -> list:
    return [t for t in tables if not any(other is not t and t in other.parents for other in tables)]


def _pick_rubric_table(tables):
    """
    The activity's grading rubric among its "Criterios de desempeño" tables:
    the only one; else the one whose nearest preceding section heading is
    "¿Cómo lo vamos a evaluar?"; else the last one. None if there's none.
    """
    if len(tables) <= 1:
        return tables[0] if tables else None
    for table in tables:
        marker = table.find_previous(string=_SECTION_MARKER_RE)
        if marker and _EVALUATION_HEADING_RE.search(marker):
            return table
    return tables[-1]


def criteria_from_table(table) -> list:
    """The criteria of one 'Criterios de desempeño | Puntos' table (header row skipped)."""
    criteria_list = []
    rows = table.find_all('tr', recursive=False)
    if not rows and table.tbody:
        rows = table.tbody.find_all('tr', recursive=False)
    if not rows and table.thead:
        rows = table.thead.find_all('tr', recursive=False)

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
    return criteria_list


def parse_rubrica_from_fragment(html: str) -> list:
    """
    The rubric inside one block of HTML (e.g. an activity the user added in
    the review panel): the innermost table mentioning 'Criterios de
    desempeño', or [] if there's none.
    """
    soup = BeautifulSoup(html, "html.parser")
    candidates = [t for t in soup.find_all('table') if 'Criterios de desempe' in t.get_text()]
    tables = [t for t in _innermost(candidates) if criteria_from_table(t)]
    chosen = _pick_rubric_table(tables)
    return criteria_from_table(chosen) if chosen is not None else []
