import os
from bs4 import BeautifulSoup

def generate_afianzamiento_html(parsed_data, template_path, output_path):
    """
    Generates the Afianzamiento HTML file using the afianzamiento template.
    """
    with open(template_path, 'r', encoding='utf-8') as f:
        template_html = f.read()
        
    soup = BeautifulSoup(template_html, "html.parser")
    container = soup.find(id="virtual-questions-container")
    
    if container:
        container.clear()
        
        afianzamiento_questions = parsed_data.get("afianzamiento", [])
        for i, q in enumerate(afianzamiento_questions):
            question_div = soup.new_tag("div", attrs={"class": "virtual-af-question"})
            question_div["data-answer"] = q.get("respuesta", "true")
            question_div["data-feedback"] = q.get("retroalimentacion") or "Respuesta registrada."
            
            p_tag = soup.new_tag("p")
            p_tag.string = q.get("pregunta", "")
            question_div.append(p_tag)
            
            # Verdadero button
            label_v = soup.new_tag("label", attrs={"class": "v-af-button"})
            label_v.string = "Verdadero"
            input_v = soup.new_tag("input", attrs={"type": "radio", "name": f"question{i}", "value": "true"})
            label_v.append(input_v)
            question_div.append(label_v)
            
            # Falso button
            label_f = soup.new_tag("label", attrs={"class": "v-af-button"})
            label_f.string = "Falso"
            input_f = soup.new_tag("input", attrs={"type": "radio", "name": f"question{i}", "value": "false"})
            label_f.append(input_f)
            question_div.append(label_f)
            
            container.append(question_div)
            
    final_html = soup.prettify(formatter="minimal")
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(final_html)
