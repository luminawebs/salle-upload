from actions.actividad_actions import parse_actividad_data, generate_actividad_html_file, _read_raw_html
import os

raw_html = _read_raw_html("assets/4735/actividades/Plantilla_Taller_S6.html")
parsed_data = parse_actividad_data(raw_html)

generate_actividad_html_file(
    parsed_data,
    "assets/templates/actividad.html",
    "assets/4735/actividades/S6_actividad_test.html"
)
print("Generated S6_actividad_test.html")
