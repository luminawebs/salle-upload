import json
import traceback
from bs4 import BeautifulSoup
from actions.infografia_parser import parse_infografia_html, generate_infografia_html

with open(r'assets/raw/VIR-INFOGRAFIA07.html', 'r', encoding='utf-8') as f:
    raw_html = f.read()

with open(r'assets/4737/contenidos.json', 'r', encoding='utf-8') as f:
    contenidos_data = json.load(f)

parsed_data = parse_infografia_html(raw_html)

course_title = contenidos_data.get("nombre", "Nombre del curso")
presentation_title = contenidos_data["Semana 7"].get("nombre", "Presentación Semana 7")

try:
    final_html = generate_infografia_html(parsed_data, "https://example.com/", 7, course_title, presentation_title)
    print("SUCCESS!")
except Exception as e:
    print("FAILED!")
    traceback.print_exc()
