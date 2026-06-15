import re
import logging
from bs4 import BeautifulSoup

from .cleaner import _sanitize_resource_section_html

logger = logging.getLogger(__name__)

def parse_foro_data(clean_html_str):
    """
    Parses the cleaned HTML by normalizing it to plain text and using regex
    boundary markers to extract each forum section.

    The WYSIWYG content coming from Moodle is Microsoft Word-converted HTML
    with heavily nested <p>, <span>, and <table> elements. Top-level element
    iteration is insufficient because the headings are buried deep in the tree.
    Plain-text + regex is the reliable approach.
    """
    parsed_data = {
        "nombre_del_foro": "",
        "descripcion": "",
        "indicaciones": "",
        "desarrollo_actividad": "XX horas",
        "consulta_materiales": "XX horas",
        "tipo_actividad": "Colaborativa",
        "recursos_basicos": "",
        "recursos_complementarios": "",
        "rol_profesor": "",
        "instrucciones_participacion": ""
    }

    if not clean_html_str:
        return parsed_data

    soup = BeautifulSoup(clean_html_str, "html.parser")

    # ── Step 1: Get flat plain text, normalize whitespace ──
    full_text = soup.get_text(separator=' ')
    norm = re.sub(r'\s+', ' ', full_text).strip()

    # ── Step 2: Truncate at "Rúbrica. Foro de discusión" ──
    rubrica_match = re.search(r'R[uú]brica[\.\s,]*Foro', norm, re.IGNORECASE)
    if rubrica_match:
        norm = norm[:rubrica_match.start()].rstrip()
        logger.info("Truncated content at 'Rúbrica. Foro de discusión'.")

    # ── Step 3: Extract fields via regex on normalized plain text ──

    # nombre_del_foro: between "Foro de discusión." and "Descripción"
    m = re.search(
        r'Foro\s+de\s+discusi[oó]n[\.\s]+(.+?)\s+Descripci[oó]n',
        norm, re.IGNORECASE)
    if m:
        parsed_data["nombre_del_foro"] = m.group(1).strip(' .')
    else:
        # Fallback if "Descripción" or "Foro de discusión" is missing
        m2 = re.search(r'abri[oó]\s+el\s+foro\s+(?:<b>)?([A-ZÁÉÍÓÚa-záéíóú\s]+?)(?:</b>|Participe|\.|\n|$)', clean_html_str)
        if m2:
            parsed_data["nombre_del_foro"] = m2.group(1).strip()
        else:
            # Try plain text fallback with a more relaxed boundary
            m3 = re.search(r'abri[oó]\s+el\s+foro\s+([A-ZÁÉÍÓÚ][a-záéíóúA-ZÁÉÍÓÚ\s]+?)(?:\s+[A-Z][a-z]|\.|$)', norm)
            if m3:
                parsed_data["nombre_del_foro"] = m3.group(1).strip()

    if parsed_data.get("nombre_del_foro"):
        logger.info(f"Extracted nombre_del_foro: {parsed_data['nombre_del_foro']}")

    # descripcion: between "Descripción" and "Indicaciones para el desarrollo"
    m = re.search(
        r'Descripci[oó]n\s+(.+?)\s+Indicaciones\s+para\s+el\s+desarrollo',
        norm, re.IGNORECASE)
    if m:
        parsed_data["descripcion"] = m.group(1).strip()
    else:
        # Fallback if "Descripción" heading is missing
        m2 = re.search(r'^(.+?)\s+Indicaciones\s+para\s+el\s+desarrollo', norm, re.IGNORECASE)
        if m2:
            desc = m2.group(1).strip()
            # Remove "Foro de discusión. NAME" if it happens to be at the start
            desc = re.sub(r'^Foro\s+de\s+discusi[oó]n[^\.]*\.?\s*', '', desc, flags=re.IGNORECASE).strip()
            parsed_data["descripcion"] = desc

    # indicaciones: between "Indicaciones para el desarrollo de la actividad"
    # and "Tiempos y recursos"
    m = re.search(
        r'Indicaciones\s+para\s+el\s+desarrollo\s+de\s+la\s+actividad\s+(.+?)'
        r'\s+Tiempos\s+y\s+recursos',
        norm, re.IGNORECASE)
    if m:
        parsed_data["indicaciones"] = m.group(1).strip()

    # desarrollo_actividad: "Desarrollo de la actividad: N horas"
    m = re.search(
        r'Desarrollo\s+de\s+la\s+actividad\s*:\s*(\d+)\s*[º°]?\s*(horas?)',
        norm, re.IGNORECASE)
    if m:
        parsed_data["desarrollo_actividad"] = f"{m.group(1)} {m.group(2)}"

    # consulta_materiales: "Consulta de materiales: N horas"
    m = re.search(
        r'Consulta\s+de\s+materiales\s*:\s*(\d+)\s*[º°]?\s*(horas?)',
        norm, re.IGNORECASE)
    if m:
        parsed_data["consulta_materiales"] = f"{m.group(1)} {m.group(2)}"

    # tipo_actividad: word(s) right after "Tipo de actividad"
    m = re.search(
        r'Tipo\s+de\s+actividad\s+([A-ZÁÉÍÓÚa-záéíóú][^\n]{1,40}?)'
        r'(?:\s{2,}|\s+Tiempos|\s+Recursos|\s+Rol)',
        norm, re.IGNORECASE)
    if m:
        parsed_data["tipo_actividad"] = m.group(1).strip()

    # recursos_basicos: between "Recurso(s) básico(s):" and "Recurso(s) complementario(s):"
    m = re.search(
        r'Recurso\(?s?\)?\s*b[aá]sico\(?s?\)?\s*:\s*(.+?)'
        r'\s*Recurso\(?s?\)?\s*complementario',
        norm, re.IGNORECASE)
    if m:
        parsed_data["recursos_basicos"] = m.group(1).strip()

    # recursos_complementarios: between "Recurso(s) complementario(s):" and "Rol del profesor:"
    m = re.search(
        r'Recurso\(?s?\)?\s*complementario\(?s?\)?\s*:\s*(.+?)'
        r'\s*Rol\s+del\s+(?:profesor|tutor)\s*:',
        norm, re.IGNORECASE)
    if m:
        parsed_data["recursos_complementarios"] = m.group(1).strip()

    # rol_profesor: between "Rol del profesor:" and "Para participar siga las instrucciones"
    m = re.search(
        r'Rol\s+del\s+(?:profesor|tutor)\s*:\s*(.+?)'
        r'\s*Para\s+participar\s+siga\s+las\s+instrucciones',
        norm, re.IGNORECASE)
    if m:
        parsed_data["rol_profesor"] = m.group(1).strip()

    # instrucciones_participacion: text after the "Para participar…" heading sentence
    m = re.search(
        r'Para\s+participar\s+siga\s+las\s+instrucciones\s+que\s+se\s+muestran'
        r'\s+a\s+continuaci[oó]n[\.\s]+(.+)',
        norm, re.IGNORECASE)
    if m:
        parsed_data["instrucciones_participacion"] = m.group(1).strip()

    # instrucciones_participacion_html: preserve HTML structure if the source includes lists
    
    
     # Al final de parse_foro_data(clean_html_str):
    parsed_data["indicaciones_html"] = _extract_indicaciones_html(soup)
    
    parsed_data["instrucciones_participacion_html"] = _extract_instrucciones_participacion_html(soup)
    parsed_data["recursos_basicos_html"] = _sanitize_resource_section_html(
        _extract_section_between_headings(
            soup,
            r'Recurso\(?s\)?\s*b[aá]sico\(?s\)?\s*:',
            [
                r'Recurso\(?s\)?\s*complementario\(?s\)?\s*:',
                r'Rol\s+del\s+(?:profesor|tutor)\s*:',
                r'R[uú]brica',
            ],
        )
    )
    parsed_data["recursos_complementarios_html"] = _sanitize_resource_section_html(
        _extract_section_between_headings(
            soup,
            r'Recurso\(?s\)?\s*complementario\(?s\)?\s*:',
            [
                r'Rol\s+del\s+(?:profesor|tutor)\s*:',
                r'R[uú]brica',
            ],
        )
    )
    
   

    # ── Step 4: Log missing sections ──
    for key, value in parsed_data.items():
        if not value:
            logger.warning(
                f"Foro parsing: Could not extract '{key}' — "
                "heading may be missing or named differently.")
            
   

    return parsed_data

def _extract_instrucciones_participacion_html(soup):
    """Extract the HTML nodes following the participation instructions heading."""
    text_node = soup.find(
        text=re.compile(
            r'Para\s+participar\s+siga\s+las\s+instrucciones\s+que\s+se\s+muestran'
            r'\s+a\s+continuaci[oó]n',
            re.IGNORECASE))
    if not text_node:
        return None

    tag = text_node.parent
    while tag and tag.name not in ["p", "li", "div"]:
        tag = tag.parent
    if not tag:
        return None

    html_fragments = []
    for sibling in tag.next_siblings:
        if isinstance(sibling, str):
            if not sibling.strip():
                continue
            # Stop if we encounter "Rúbrica" text
            if re.search(r'R[uú]brica', sibling, re.IGNORECASE):
                break
            html_fragments.append(sibling)
            continue
        if sibling.name in ["h3", "h4", "table"]:
            break
        html_fragments.append(str(sibling))

    extracted_html = ''.join(html_fragments).strip()
    if not extracted_html:
        return None

    # Clean up invalid <p> tags inside <li> elements
    instructions_soup = BeautifulSoup(extracted_html, "html.parser")
    for li in instructions_soup.find_all("li"):
        for p in li.find_all("p"):
            p.unwrap()  # Remove <p> tags but keep their contents

    return str(instructions_soup)

def _extract_section_html(soup, heading_regex):
    """
    Extract section HTML using position-based traversal instead of sibling-based.
    This is robust against malformed Word/Moodle HTML.
    """
    # 1. Flatten all relevant nodes in order
    all_nodes = []
    for el in soup.body.descendants if soup.body else soup.descendants:
        if getattr(el, "name", None) in ["p", "div", "ul", "ol", "li", "table", "h1", "h2", "h3", "h4", "h5", "h6"]:
            all_nodes.append(el)

    # 2. Find the heading index
    start_idx = None
    for i, node in enumerate(all_nodes):
        text = node.get_text(strip=True)
        if re.search(heading_regex, text, re.IGNORECASE):
            start_idx = i
            break

    if start_idx is None:
        logger.warning(f"Heading not found for regex: {heading_regex}")
        return None

    # 3. Collect content AFTER the heading
    html_fragments = []
    collected_nodes = set()

    for node in all_nodes[start_idx + 1:]:
        text = node.get_text(" ", strip=True).lower()

        # 4. Define strong stop conditions (REAL section boundaries)
        if re.search(
            r'(rol\s+del\s+(?:profesor|tutor)|r[uú]brica|indicaciones\s+para\s+el\s+desarrollo|tiempos\s+y\s+recursos)',
            text,
            re.IGNORECASE
        ):
            break

        is_child = False
        parent = node.parent
        while parent:
            if parent in collected_nodes:
                is_child = True
                break
            parent = parent.parent

        if not is_child:
            html_fragments.append(str(node))
            collected_nodes.add(node)

    extracted_html = ''.join(html_fragments).strip()

    logger.info(f"[POSITIONAL] Extracted '{heading_regex}' → {len(extracted_html)} chars")

    return extracted_html if extracted_html else None

def _extract_section_between_headings(soup, start_heading_regex, stop_heading_regexes):
    """
    Extract section HTML between an explicit start heading and one of the stop headings.
    """
    all_nodes = []
    for el in soup.body.descendants if soup.body else soup.descendants:
        if getattr(el, "name", None) in [
            "p", "div", "ul", "ol", "li", "table", "h1", "h2", "h3", "h4", "h5", "h6"
        ]:
            all_nodes.append(el)

    start_idx = None
    for i, node in enumerate(all_nodes):
        text = node.get_text(" ", strip=True)
        if re.search(start_heading_regex, text, re.IGNORECASE):
            start_idx = i
            break

    if start_idx is None:
        logger.warning(f"Start heading not found for regex: {start_heading_regex}")
        return None

    html_fragments = []
    collected_nodes = set()
    for node in all_nodes[start_idx + 1:]:
        text = node.get_text(" ", strip=True)
        if any(re.search(stop_re, text, re.IGNORECASE) for stop_re in stop_heading_regexes):
            break
            
        is_child = False
        parent = node.parent
        while parent:
            if parent in collected_nodes:
                is_child = True
                break
            parent = parent.parent
            
        if not is_child:
            html_fragments.append(str(node))
            collected_nodes.add(node)

    extracted_html = "".join(html_fragments).strip()
    return extracted_html if extracted_html else None

def _resource_html_has_reference_content(html_text):
    """
    Returns True when extracted resource HTML still contains substantive citation text.
    """
    if not html_text:
        return False

    text = " ".join(BeautifulSoup(html_text, "html.parser").get_text(" ", strip=True).split())
    if not text:
        return False

    noise_cleanup = re.sub(
        r'(?i)\b(tipo\s+de\s+actividad|colaborativa|tiempos|desarrollo\s+de\s+la\s+actividad\s*:?\s*\d*\s*horas?|'
        r'consulta\s+de\s+materiales\s*:?\s*\d*\s*horas?|recursos?|'
        r'recurso\(?s?\)?\s*b[aá]sico\(?s?\)?\s*:?|recurso\(?s?\)?\s*complementario\(?s?\)?\s*:?)\b',
        " ",
        text,
    )
    noise_cleanup = re.sub(r'\s+', ' ', noise_cleanup).strip(" .,:;-")
    return len(noise_cleanup) >= 25

def _extract_indicaciones_html(soup):
    """
    Extrae el HTML de las indicaciones manteniendo listas (ul, ol, li)
    y negritas (b, strong), pero eliminando <p> dentro de <li>.
    """
    text_node = soup.find(text=re.compile(r'Indicaciones\s+para\s+el\s+desarrollo\s+de\s+la\s+actividad', re.IGNORECASE))
    if not text_node:
        return None

    title_tag = text_node.parent
    while title_tag and title_tag.name not in ["h1", "h2", "h3", "h4", "p", "div"]:
        title_tag = title_tag.parent
    if not title_tag:
        return None

    html_fragments = []
    
    for sibling in title_tag.next_siblings:
        if isinstance(sibling, str):
            if not sibling.strip():
                continue
            html_fragments.append(sibling)
            continue
        
        sibling_text = sibling.get_text().strip().lower()
        
        # Stop when we hit major section boundaries
        if sibling.name in ["h1", "h2", "h3", "h4"]:
            if re.search(r'(tiempos\s+y\s+recursos|recursos\s+(b[aá]sicos|complementarios)|rol\s+del\s+profesor|r[uú]brica)', sibling_text, re.IGNORECASE):
                break
        
        # Also stop when encountering a paragraph that clearly starts a new major section
        if sibling.name == "p" and re.search(r'^(tiempos\s+y\s+recursos|recursos\s+(b[aá]sicos|complementarios))', sibling_text, re.IGNORECASE):
            break
        
        html_fragments.append(str(sibling))
    
    extracted_html = ''.join(html_fragments).strip()
    
    # Clean the extracted HTML
    if extracted_html:
        indicaciones_soup = BeautifulSoup(extracted_html, "html.parser")
        
        # Remove <p> tags inside <li> but keep their contents
        for li in indicaciones_soup.find_all("li"):
            for p in li.find_all("p"):
                p.unwrap()  # Remove <p> tag, keep inner content
        
        # Also unwrap any <p> that might be direct children of <ul> or <ol>
        for ul_ol in indicaciones_soup.find_all(["ul", "ol"]):
            for p in ul_ol.find_all("p", recursive=False):
                p.unwrap()
        
        return str(indicaciones_soup)
    
    return extracted_html if extracted_html else None
