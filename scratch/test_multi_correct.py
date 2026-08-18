import os
from actions.html_transformer import extract_questions_from_html_to_moodle_xml

test_html = """
<p>PREGUNTA 5 (Opción Múltiple con múltiples correctas)</p>
<p>Tipo: multiple</p>
<p>Enunciado: ¿Cuáles de los siguientes son gases nobles?</p>
<p>Opciones:</p>
<p>=Helio</p>
<p>=Neón</p>
<p>=Argón</p>
<p>=Kríptón</p>
<p>=Xenón</p>
<p>=Radón</p>
<p>Oxígeno</p>
<p>Nitrógeno</p>
"""

out_xml = "scratch/test_multi_correct.xml"
extract_questions_from_html_to_moodle_xml(test_html, out_xml, 999, "test_doc")

with open(out_xml, "r", encoding="utf-8") as f:
    print(f.read())
