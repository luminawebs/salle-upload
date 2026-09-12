import sys
import os
sys.path.append('.')
from core.data_parser import parse_docx_to_html, run_docx_splitting_workflow
from actions.html_transformer import extract_questions_from_html_to_moodle_xml

course_id = 9999
docx_path = r'd:\29 LA SALLE\automatizacion_selenium_SALLE-frontend\assets\doc-course-test\v10\D.P. Ejecución, Control y Cierre de Proyectos.docx'

# Create dummy workspace
base_dir = os.path.join("workspace", str(course_id))
os.makedirs(base_dir, exist_ok=True)

# Fake the docx location since run_docx_parsing_workflow expects it in the workspace
import shutil
shutil.copy(docx_path, os.path.join(base_dir, f"{course_id}.docx"))

# Run extraction and splitting
from core.data_parser import run_docx_parsing_workflow
try:
    run_docx_parsing_workflow(course_id)
    run_docx_splitting_workflow(course_id)
except Exception as e:
    print(f"Workflow Error: {e}")

# Now check Actividad 3
act3_path = os.path.join(base_dir, "actividades", "actividad3.html")
if os.path.exists(act3_path):
    with open(act3_path, "r", encoding="utf-8") as f:
        html = f.read()
    q_count = extract_questions_from_html_to_moodle_xml(html, course_id=course_id)
    print(f"Actividad 3 parsed {q_count} questions.")
else:
    print("Actividad 3 HTML not generated.")

# Now check Actividad 6
act6_path = os.path.join(base_dir, "actividades", "actividad6.html")
if os.path.exists(act6_path):
    with open(act6_path, "r", encoding="utf-8") as f:
        html = f.read()
    q_count = extract_questions_from_html_to_moodle_xml(html, course_id=course_id)
    print(f"Actividad 6 parsed {q_count} questions.")
else:
    print("Actividad 6 HTML not generated.")
