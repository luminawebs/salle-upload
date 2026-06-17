from bs4 import BeautifulSoup
import re

html = """
<p>Explore el recurso web “Wireframes”. Disponible <a href="https://miro.com/es/wireframe/que-es-wireframe/" target="_blank" rel="noopener">Wireframe</a>.</p>
<p>Read this book: <a href="http://example.com">Example</a>.</p>
"""

soup = BeautifulSoup(html, 'html.parser')

for a_tag in soup.find_all("a"):
    a_tag['target'] = "_blank"
    a_tag.string = "(disponible aquí)"
    
    prev_node = a_tag.previous_sibling
    if prev_node and isinstance(prev_node, str):
        new_text = re.sub(r'(?i)\s*disponible\s*:?\s*$', ' ', prev_node)
        if new_text == prev_node:
            new_text = re.sub(r'\s*:\s*$', ' ', prev_node)
        
        if new_text != prev_node:
            prev_node.replace_with(new_text)

print(str(soup))
