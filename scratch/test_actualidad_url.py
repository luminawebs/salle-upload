import sys
sys.path.append(r'd:\28 Uniminuto\automatizacion_selenium_fase02')
from actions.actualidad_actions import clean_actualidad_html, sanitize_actualidad_output, extract_actualidad_items
from bs4 import BeautifulSoup

html = '''<p>Test item. <a href="https://elibro.net/123">Link</a></p>'''
print('Original:', html)
c1 = clean_actualidad_html(html)
print('clean_actualidad_html:', c1)
c2 = sanitize_actualidad_output(c1)
print('sanitize_actualidad_output:', c2)
items = extract_actualidad_items(c2)
print('extract_actualidad_items:', items)
