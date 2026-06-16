import bs4, re

def parse_intro(html):
    soup = bs4.BeautifulSoup(html, "html.parser")
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
            
            # Identify if it's Resumen or Preguntas
            is_resumen = td0_text.startswith("RESUMEN")
            is_preguntas = td0_text.startswith("PREGUNTAS ORIENTADORAS")
            
            if is_resumen or is_preguntas:
                if len(tds) >= 2:
                    content_td = tds[1]
                else:
                    # Content is merged into the first TD. We should remove the heading "RESUMEN:" or similar
                    content_td = bs4.BeautifulSoup(str(tds[0]), "html.parser").td
                    # Find the first text node or tag containing the heading and strip it
                    # The easiest way is to use regex substitution on the raw HTML
                    raw = str(content_td)
                    if is_resumen:
                        raw = re.sub(r'(<[^>]+>)*RESUMEN[:\s]*(<[^>]+>)*', '', raw, count=1, flags=re.IGNORECASE)
                    else:
                        raw = re.sub(r'(<[^>]+>)*PREGUNTAS ORIENTADORAS[:\s]*(<[^>]+>)*', '', raw, count=1, flags=re.IGNORECASE)
                    content_td = bs4.BeautifulSoup(raw, "html.parser")

                if is_resumen:
                    resumen_ps = [p.get_text(strip=True) for p in content_td.find_all('p') if p.get_text(strip=True)]
                    if not resumen_ps:
                        text_only = content_td.get_text(strip=True)
                        if text_only:
                            resumen_ps = [text_only]
                    unidades[current_unidad]["resumen"] = resumen_ps

                elif is_preguntas:
                    raw_html = str(content_td)
                    raw_html = re.sub(r'<(br|/p|/div|/li)[^>]*>', '|||', raw_html, flags=re.IGNORECASE)
                    clean_text = bs4.BeautifulSoup(raw_html, "html.parser").get_text(separator=' ')
                    
                    parts = re.split(r'\|\|\||[\uf0b7•·\n]+', clean_text)
                    
                    for part in parts:
                        pt = part.strip()
                        pt = re.sub(r'^[\uf0b7•·\-\*\s]+', '', pt)
                        if pt:
                            unidades[current_unidad]["preguntas"].append(pt)

    for k, v in unidades.items():
        print(f"--- {k} ---")
        print("Resumen:", v['resumen'])
        print("Preguntas:", v['preguntas'])

parse_intro(open('test_guia2.html', 'r', encoding='utf-8').read())
