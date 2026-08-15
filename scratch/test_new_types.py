import os
from actions.html_transformer import extract_questions_from_html_to_moodle_xml

test_html = """
<p>Pregunta 1:</p>
<p>Tipo: completar</p>
<p>La capital de Colombia es [Bogotá].</p>
<p>Retroalimentación correcta: ¡Muy bien!</p>

<p>Pregunta 2:</p>
<p>Tipo: arrastrar_soltar</p>
<p>El planeta más grande es [[1]] y el planeta rojo es [[2]].</p>
<p>Opciones:</p>
<p>=Júpiter</p>
<p>=Marte</p>
<p>Venus</p>
"""

out_xml = "scratch/test_new_types.xml"
extract_questions_from_html_to_moodle_xml(test_html, out_xml, 999, "test_doc")

with open(out_xml, "r", encoding="utf-8") as f:
    print(f.read())
