import sys
import os

# Add the project root to sys.path
sys.path.append(os.path.abspath("."))

from core.data_parser import parse_docx_to_html, run_docx_splitting_workflow
from actions.html_transformer import extract_questions_from_html_to_moodle_xml
from bs4 import BeautifulSoup

course_id = 99999
docx_path = r"d:\29 LA SALLE\automatizacion_selenium_SALLE-frontend\assets\doc-course-test\v7\DP. Lenguaje de programacioìn I 2026.docx"
workspace_dir = os.path.join("workspace", str(course_id))
os.makedirs(workspace_dir, exist_ok=True)
output_html = os.path.join(workspace_dir, "raw_docx_extracted.html")

# 1. Parse docx
print(f"Parsing DOCX: {docx_path}")
html_content = parse_docx_to_html(docx_path, course_id)
with open(output_html, "w", encoding="utf-8") as f:
    f.write(html_content)
print(f"Saved HTML to {output_html}")

# 2. Split DOCX
print("Splitting DOCX...")
with open(output_html, "w", encoding="utf-8") as f:
    f.write(html_content)
run_docx_splitting_workflow(course_id)

# 3. Test question extraction on each activity
act_dir = os.path.join(workspace_dir, "actividades")
if not os.path.exists(act_dir):
    print("No actividades found!")
else:
    for filename in sorted(os.listdir(act_dir)):
        if filename.endswith(".html"):
            file_path = os.path.join(act_dir, filename)
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            # print snippet of content to see if "Cuestionario" is there
            if "Pregunta" in content or "pregunta" in content.lower():
                print(f"Testing questions on {filename}...")
                xml_out = os.path.join(workspace_dir, f"{filename}_questions.xml")
                q_count = extract_questions_from_html_to_moodle_xml(content, xml_out, course_id, "doc")
                print(f" -> Found {q_count} questions in {filename}.")
