from bs4 import BeautifulSoup
import re

html_path = "test_guia.html"

with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

soup = BeautifulSoup(html, "html.parser")
rubricas = {}

for tr in soup.find_all("tr", recursive=True):
    tr_text = tr.get_text(strip=True).upper()
    actividad_match = re.search(r'ACTIVIDAD\s*(\d+)', tr_text)
    if actividad_match and "ACTIVIDADES DE APRENDIZAJE" not in tr_text:
        act_num = int(actividad_match.group(1))
        
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
            # Only direct rows to avoid processing rows from nested tables as main rows
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
                    print(f"Act {act_num} Row {i}: Criterio: {criterio_text[:30]}... | Puntos: '{puntos_text}'")
