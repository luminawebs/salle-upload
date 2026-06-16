from bs4 import BeautifulSoup
import sys

html_file = "d:\\29 LA SALLE\\automatizacion_selenium_SALLE-frontend\\assets\\example_course\\tableoutput_unedited.html"

with open(html_file, 'r', encoding='utf-8') as f:
    soup = BeautifulSoup(f.read(), 'html.parser')

tables = soup.find_all('table')
for idx, table in enumerate(tables):
    print(f"Table {idx}")
    for r_idx, row in enumerate(table.find_all('tr')):
        cols = row.find_all(['td', 'th'])
        col_spans = sum(int(c.get('colspan', 1)) for c in cols)
        print(f"  Row {r_idx}: {len(cols)} cells, spans {col_spans} logical cols")
