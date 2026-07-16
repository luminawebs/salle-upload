import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom

def build_moodle_xml(questions, category_name="Default Category"):
    """
    Builds a Moodle XML string for a list of parsed questions.
    This provides a foundation for extending the export capabilities.
    """
    quiz = ET.Element("quiz")
    
    # Add category
    question_category = ET.SubElement(quiz, "question", type="category")
    category_text = ET.SubElement(question_category, "category")
    text_elem = ET.SubElement(category_text, "text")
    text_elem.text = f"$course$/{category_name}"
    
    for q in questions:
        # Determine question type
        is_truefalse = False
        if len(q["opciones"]) == 2:
            opts = [o.lower() for o in q["opciones"]]
            if any("verdadero" in o for o in opts) and any("falso" in o for o in opts):
                is_truefalse = True
                
        q_type = "truefalse" if is_truefalse else "multichoice"
        
        question = ET.SubElement(quiz, "question", type=q_type)
        
        name = ET.SubElement(question, "name")
        name_text = ET.SubElement(name, "text")
        name_text.text = q.get("pregunta", "Question")[:50] + "..." # Short name
        
        questiontext = ET.SubElement(question, "questiontext", format="html")
        qtext_text = ET.SubElement(questiontext, "text")
        qtext_text.text = f"<![CDATA[{q.get('pregunta', '')}]]>"
        
        if q.get("retroalimentacion"):
            generalfeedback = ET.SubElement(question, "generalfeedback", format="html")
            fb_text = ET.SubElement(generalfeedback, "text")
            fb_text.text = f"<![CDATA[{q.get('retroalimentacion')}]]>"
            
        for opt in q["opciones"]:
            # Basic logic: if opt matches the saved answer, it's 100%, else 0%
            is_correct = False
            ans_val = q.get("respuesta")
            if is_truefalse:
                is_correct = (opt.lower() == "verdadero" and ans_val == "true") or \
                             (opt.lower() == "falso" and ans_val == "false")
            else:
                is_correct = (opt == ans_val)
                
            fraction = "100" if is_correct else "0"
            answer = ET.SubElement(question, "answer", fraction=fraction, format="html")
            ans_text = ET.SubElement(answer, "text")
            ans_text.text = f"<![CDATA[{opt}]]>"
            
    # Pretty print XML
    rough_string = ET.tostring(quiz, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    # Return string without the minidom generated XML declaration if desired, 
    # but standard XML declaration is fine.
    return reparsed.toprettyxml(indent="  ")
