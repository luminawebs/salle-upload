import os
import json
import re
from bs4 import BeautifulSoup
from glob import glob

TEMPLATE = """<!--Introducción-->


<!--Navegación-->
<ul class="nav nav-pills virtual-nav-pills" id="pills-tab" role="tablist">
    <!--1-->
    <li class="nav-item virtual-nav-tab" role="presentation">
        <button class="nav-link virtual-nav-link active" id="pills-home-tab" data-bs-toggle="pill"
            data-bs-target="#pills-virtual-1" type="button" role="tab" aria-controls="pills-virtual-1"
            aria-selected="true">Introducción</button>
    </li>
    <!--2-->
    <li class="nav-item virtual-nav-tab" role="presentation">
        <button class="nav-link virtual-nav-link" id="pills-profile-tab" data-bs-toggle="pill"
            data-bs-target="#pills-virtual-2" type="button" role="tab" aria-controls="pills-virtual-2"
            aria-selected="false" tabindex="-1">Resultados de aprendizaje</button>
    </li>
    <!--3-->
    <li class="nav-item virtual-nav-tab" role="presentation">
        <button class="nav-link virtual-nav-link" id="pills-contact-tab" data-bs-toggle="pill"
            data-bs-target="#pills-virtual-3" type="button" role="tab" aria-controls="pills-virtual-3"
            aria-selected="false" tabindex="-1">Contenido temático</button>
    </li>
</ul>

<!--Contenido-->
<div class="tab-content virtual-tab-content virtual-tab-border" id="pills-tabContent">

    <!--1-->
    <div class="tab-pane fade show active" id="pills-virtual-1" role="tabpanel" aria-labelledby="pills-virtual-1">
        <div class="virtual-txt">
            <h3>Introducción</h3>
{introduccion_html}
        </div>
    </div>
    <!--2-->
    <div class="tab-pane fade" id="pills-virtual-2" role="tabpanel" aria-labelledby="pills-virtual-2">
        <div class="virtual-txt">
            <h3>Resultados de aprendizaje</h3>
            {resultados_msg}
            <p><b>{rac}</b>
            </p>
            <ul class="virtual-ul">
{criterios_li}
            </ul>
        </div>
    </div>
    <!--3-->
    <div class="tab-pane fade" id="pills-virtual-3" role="tabpanel" aria-labelledby="pills-virtual-3">
        <div class="virtual-txt">
            <h3>Contenido temático de la semana</h3>
            {subtemas_msg}

            <p><b>Unidad {unidad_num}. {tema}</b></p>
            <ul class="virtual-ul">
{subtemas_li}
            </ul>
        </div>
    </div>

</div>
"""

def clean_html(html_str):
    """
    Cleans (does not remove) the HTML code.
    It formats it properly and closes unclosed tags.
    """
    if not html_str or not str(html_str).strip():
        return ""
    soup = BeautifulSoup(str(html_str), "html.parser")
    # indent properly to fit within the div
    return "\n".join("            " + line for line in soup.prettify().splitlines())

def wrap_bibliographic_title_in_bold(html_text: str) -> str:
    """
    Wraps the book title (text after the year/date up to the next period/comma or inside <i>/<em>) in <b>.
    Supports formats like (YYYY)., (s.f.)., (n.d.)., (YYYY, Month). etc.
    """
    if not html_text:
        return html_text
    
    soup = BeautifulSoup(html_text, "html.parser")
    for tag in soup.find_all(["p", "li"]):
        # Skip nested paragraphs or list items to avoid double processing
        if tag.find_parent(["p", "li"]):
            continue
            
        inner_html = "".join(str(c) for c in tag.contents)
        # Match dates like (2023), (s.f.), (n.d.), (2023, mayo)
        match = re.search(r'(\((?:\d{4}|s\.f\.|n\.d\.)(?:[^)]*)\)[.,]\s*)', inner_html, re.IGNORECASE)
        if match:
            prefix = inner_html[:match.end()]
            rest = inner_html[match.end():]

            tag_match = re.match(r'^(<i[^>]*>.*?</i>|<em[^>]*>.*?</em>)', rest, flags=re.IGNORECASE)
            if tag_match:
                title = tag_match.group(1)
                suffix = rest[len(title):]
                tag.clear()
                tag.append(BeautifulSoup(f"{prefix}<b>{title}</b>{suffix}", "html.parser"))
                continue
            
            period_match = re.match(r'^([^.]+?\.)', rest)
            if period_match:
                title = period_match.group(1)
                suffix = rest[len(title):]
                tag.clear()
                tag.append(BeautifulSoup(f"{prefix}<b>{title}</b>{suffix}", "html.parser"))
                continue

            comma_match = re.match(r'^([^,]+?,)', rest)
            if comma_match:
                title = comma_match.group(1)
                suffix = rest[len(title):]
                tag.clear()
                tag.append(BeautifulSoup(f"{prefix}<b>{title}</b>{suffix}", "html.parser"))
                continue

    return str(soup)

def process_contenidos(base_dir):
    """
    Automatically processes diferentes folders containing contenidos.json
    and outputs the respective HTML files.
    """
    search_pattern = os.path.join(base_dir, "*", "contenidos.json")
    json_files = glob(search_pattern)
    
    if not json_files:
        print(f"No contenidos.json files found in {base_dir}/*/")
        return
        
    for json_path in json_files:
        with open(json_path, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                print(f"Error reading JSON from {json_path}")
                continue
        
        folder = os.path.dirname(json_path)
        print(f"Processing {json_path}...")
        
        temas_seen = {}
        unidad_counter = 1
        
        for semana_key, semana_data in data.items():
            # Parse semana number (e.g. "Semana 1" -> 1)
            match = re.search(r'\d+', semana_key)
            if not match:
                continue
            semana_num = int(match.group())
            
            # --- Tab 1: Introducción ---
            introduccion_raw = semana_data.get("introduccion", "")
            nombre = semana_data.get("nombre", "")
            
            # Fallback for missing introduction to at least show the bold title
            if not introduccion_raw.strip():
                introduccion_raw = f"<p><b>Semana {semana_num}. {nombre}</b></p>"
                
            introduccion_html = clean_html(introduccion_raw)
            
            # --- Tab 2: Resultados de aprendizaje ---
            criterios = semana_data.get("criterios", [])
            if len(criterios) == 1:
                resultados_msg = "<p>El resultado de aprendizaje de la semana es:</p>"
            else:
                resultados_msg = "<p>Los resultados de aprendizaje de la semana son:</p>"
                
            criterios_li = "\n".join(f"                <li>{c}</li>" for c in criterios)
            rac = semana_data.get("rac", "")
            
            # --- Tab 3: Contenido temático ---
            subtemas = semana_data.get("subtemas", [])
            if len(subtemas) == 1:
                subtemas_msg = "<p>En el siguiente apartado encontrará el contenido temático de esta semana.</p>"
            else:
                subtemas_msg = "<p>En el siguiente apartado encontrará los contenidos temáticos de esta semana.</p>"
                
            # Remove numbering like "1.1 " or "2.3 " from subtemas
            cleaned_subtemas = [re.sub(r'^\d+\.\d+\s*', '', s) for s in subtemas]
            subtemas_li = "\n".join(f"                <li>{s}</li>" for s in cleaned_subtemas)
            
            tema = semana_data.get("tema", "")
            if tema not in temas_seen:
                temas_seen[tema] = unidad_counter
                unidad_counter += 1
            unidad_num = temas_seen[tema]
            
            # Generate the final HTML output
            html_output = TEMPLATE.format(
                introduccion_html=introduccion_html,
                resultados_msg=resultados_msg,
                rac=rac,
                criterios_li=criterios_li,
                subtemas_msg=subtemas_msg,
                unidad_num=unidad_num,
                tema=tema,
                subtemas_li=subtemas_li
            )
            
            # Pad zero for the file name (e.g. semana_introduccion_01.html)
            out_filename = f"semana_introduccion_{semana_num:02d}.html"
            out_path = os.path.join(folder, out_filename)
            
            with open(out_path, "w", encoding="utf-8") as out_f:
                out_f.write(html_output)
                
            print(f"  Created {out_filename}")

if __name__ == "__main__":
    # Point this to the root directory where the numbered folders are.
    # We will assume the script is in 'html_generator' and the folders are in 'assets'
    current_dir = os.path.dirname(os.path.abspath(__file__))
    assets_dir = os.path.join(os.path.dirname(current_dir), "assets")
    
    print(f"Looking for 'contenidos.json' files inside numbered folders in {assets_dir}")
    process_contenidos(assets_dir)
