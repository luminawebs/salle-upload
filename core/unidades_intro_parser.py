import os
import re
import logging
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

def run_unidades_intro_splitting_workflow(course_id: int):
    """
    Parses the raw extracted docx HTML to extract the 'Resumen' and 'Preguntas orientadoras'
    for each Unidad and saves them to styled HTML fragments.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    assets_dir = os.path.join(base_dir, "assets", str(course_id))
    raw_html_path = os.path.join(assets_dir, "raw_docx_extracted.html")
    intro_dir = os.path.join(assets_dir, "introduccion")

    if not os.path.exists(raw_html_path):
        logger.error(f"Cannot perform Unidades Intro splitting. {raw_html_path} does not exist.")
        return

    os.makedirs(intro_dir, exist_ok=True)

    with open(raw_html_path, "r", encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, "html.parser")
    unidades = {}
    current_unidad = None

    for tr in soup.find_all("tr"):
        text = tr.get_text(strip=True).upper()
        # Look for UNIDAD DIDACTICA or UNIDAD
        match = re.search(r'UNIDAD\s*(?:DID\u00c1CTICA)?\s*(\d+)', text)
        if match:
            current_unidad = f"UNIDAD {match.group(1)}"
            if current_unidad not in unidades:
                unidades[current_unidad] = {"resumen": [], "preguntas": []}
            continue

        if current_unidad:
            tds = tr.find_all("td", recursive=False)
            if not tds:
                continue

            td0_text = tds[0].get_text(strip=True).upper()
            is_resumen = td0_text.startswith("RESUMEN")
            is_preguntas = td0_text.startswith("PREGUNTAS ORIENTADORAS")

            if is_resumen or is_preguntas:
                if len(tds) >= 2:
                    content_td = tds[1]
                else:
                    # Content is merged into the first TD. Remove the heading text.
                    content_td = tds[0]
                    if is_resumen:
                        pattern = re.compile(r'^[\s]*RESUMEN[:\s]*', re.IGNORECASE)
                    else:
                        pattern = re.compile(r'^[\s]*PREGUNTAS ORIENTADORAS[:\s]*', re.IGNORECASE)
                    
                    for text_node in content_td.find_all(string=True):
                        if pattern.search(text_node):
                            text_node.replace_with(pattern.sub('', text_node))
                            break

                if is_resumen:
                    # Extract text from p tags
                    resumen_ps = [p.get_text(strip=True) for p in content_td.find_all('p') if p.get_text(strip=True)]
                    if not resumen_ps:
                        text_only = content_td.get_text(strip=True)
                        if text_only:
                            resumen_ps = [text_only]
                    unidades[current_unidad]["resumen"] = resumen_ps

                elif is_preguntas:
                    # Robust extraction: get raw HTML, replace breaks with delimiter, parse, split by delimiter and bullets
                    raw_html = str(content_td)
                    raw_html = re.sub(r'<(br|/p|/div|/li)[^>]*>', '|||', raw_html, flags=re.IGNORECASE)
                    clean_text = BeautifulSoup(raw_html, "html.parser").get_text(separator=' ')
                    
                    # \uf0b7 is Wingdings bullet. Include other common bullet chars.
                    parts = re.split(r'\|\|\||[\uf0b7•·\n]+', clean_text)
                    
                    for part in parts:
                        pt = part.strip()
                        # remove leading bullets, dashes, or asterisks
                        pt = re.sub(r'^[\uf0b7•·\-\*\s]+', '', pt)
                        if pt:
                            unidades[current_unidad]["preguntas"].append(pt)

    # Generate styled HTML files
    for unidad_key, data in unidades.items():
        if not data["resumen"] and not data["preguntas"]:
            continue

        match = re.search(r'(\d+)', unidad_key)
        if not match:
            continue
        unidad_num = match.group(1)

        html_parts = []
        for p_text in data["resumen"]:
            html_parts.append(
                f'<p><span style="font-family: tahoma, arial, helvetica, sans-serif; font-size: small; color: #000000;">{p_text}</span></p>'
            )

        if data["preguntas"]:
            html_parts.append(
                '<p><strong><span style="font-family: tahoma, arial, helvetica, sans-serif; font-size: small; color: #000000;">Las preguntas que orientarán esta unidad son:</span></strong></p>'
            )
            html_parts.append('<ul>')
            for q_text in data["preguntas"]:
                html_parts.append(
                    f'  <li><span style="font-family: tahoma, arial, helvetica, sans-serif; font-size: small; color: #000000;">{q_text}</span></li>'
                )
            html_parts.append('</ul>')

        final_html = "\n".join(html_parts)
        filename = f"introduccion_unidad_{unidad_num}.html"
        file_path = os.path.join(intro_dir, filename)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(final_html)

        logger.info(f"  ✓ Extracted {filename}")

    logger.info("  ✓ Unidades Intro splitting workflow completed.")
