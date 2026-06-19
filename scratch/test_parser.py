import mammoth
from bs4 import BeautifulSoup
import re

docx_path = r"d:\29 LA SALLE\automatizacion_selenium_SALLE-frontend\assets\doc-course-test\v2\DP_Fundamentos de internacionalización.docx"

with open(docx_path, "rb") as docx_file:
    result = mammoth.convert_to_html(docx_file)
    html = result.value
    
soup = BeautifulSoup(html, "html.parser")

found = False
for el in soup.find_all(['p', 'h1', 'h2', 'h3', 'table']):
    text = el.get_text().upper()
    if 'METODOL' in text:
        print(f"FOUND METODOLOGIA in <{el.name}>: {text[:100]}")
        found = True

with open("scratch_output.html", "w", encoding="utf-8") as f:
    f.write(html)
