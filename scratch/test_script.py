import re
from bs4 import BeautifulSoup

soup = BeautifulSoup(open('assets/doc-course-test/raw_docx_extracted.html', encoding='utf-8'), 'html.parser')
acts = []
for el in soup.find_all(['p', 'h1', 'h2', 'h3']):
    text = el.get_text().strip()
    if text.upper().startswith('ACTIVIDAD') and not text.upper().startswith('ACTIVIDADES'):
        name_part = text
        # If the name is just "ACTIVIDAD X:" or very short
        if text.strip().endswith(':') or len(text.strip()) < 15:
            nxt = el.find_next_sibling(['p', 'h1', 'h2', 'h3'])
            if nxt and nxt.get_text().strip() and not nxt.get_text().strip().upper().startswith('ACTIVIDAD'):
                name_part = text.strip() + ' ' + nxt.get_text().strip()
        acts.append(name_part)

print('\n'.join(acts))
