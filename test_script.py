import sys; sys.path.append(r'd:\29 LA SALLE\automatizacion_selenium_SALLE-frontend')
from core.data_parser import parse_docx_to_html
from actions.html_transformer import extract_questions_from_html_to_gift
import re

html = parse_docx_to_html(r'd:\29 LA SALLE\automatizacion_selenium_SALLE-frontend\assets\doc-course-test\v2\DP_Fundamentos de internacionalización.docx', 'test_123')
m = list(re.finditer(r'(ACTIVIDAD 9.*?)(UNIDAD DIDÁCTICA|$)', html, re.DOTALL | re.IGNORECASE))[1]
html_content = m.group(1)

success = extract_questions_from_html_to_gift(html_content, r'd:\29 LA SALLE\automatizacion_selenium_SALLE-frontend\test_gift.txt')
print("Success:", success)
with open(r'd:\29 LA SALLE\automatizacion_selenium_SALLE-frontend\test_gift.txt', 'r', encoding='utf-8') as f:
    print(f.read())
