import sys
import os
from bs4 import BeautifulSoup
import re

file_path = r"d:\29 LA SALLE\automatizacion_selenium_SALLE-frontend\assets\70801\actividades\actividad7.html"
with open(file_path, "r", encoding="utf-8") as f:
    html = f.read()

soup = BeautifulSoup(html, "html.parser")
xml_questions = []

def process_image_src(html, course_id):
    return html

def add_question(q_num, stem, options, is_tf, is_true, feedback=None):
    xml_questions.append({
        "num": q_num,
        "stem": stem,
        "options": options
    })
    print(f"Added Q{q_num}: {stem[:50]}... | Options: {len(options)}")

q_num = 1
# FORMAT B LOGIC
import copy
lists = soup.find_all(['ol', 'ul'])
for lst in lists:
    lis = lst.find_all('li', recursive=False)
    has_respuesta = any("(respuesta" in li.get_text(strip=True).lower() for li in lis)
    is_nested = any(li.find(['ol', 'ul']) for li in lis)
    if has_respuesta and is_nested:
        for li in lis:
            inner_list = li.find(['ol', 'ul'])
            if not inner_list: continue
            
            li_clone = copy.copy(li)
            if li_clone.find(['ol', 'ul']):
                li_clone.find(['ol', 'ul']).decompose()
            stem_html = process_image_src(li_clone.decode_contents(), None)
            
            options = []
            for inner_li in inner_list.find_all('li', recursive=False):
                opt_html = process_image_src(inner_li.decode_contents(), None)
                is_correct = False
                if "(respuesta" in inner_li.get_text().lower():
                    is_correct = True
                    opt_html = re.sub(r'(?i)\s*\((respuesta|respuesta correcta)\)', '', opt_html).strip()
                options.append((opt_html, is_correct))
            
            # THE PROBLEM MIGHT BE HERE:
            stem_text = BeautifulSoup(stem_html, "html.parser").get_text(strip=True)
            print(f"DEBUG: Evaluated nested li. Stem text: '{stem_text}'")
            if stem_text and options:
                add_question(q_num, stem_html, options, False, False)
                q_num += 1

print(f"Total questions extracted: {len(xml_questions)}")
