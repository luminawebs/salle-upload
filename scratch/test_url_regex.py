import re
from bs4 import BeautifulSoup

html = '<p>Texto Disponível em: https://google.com final y tambien www.yahoo.com y <a href="https://bing.com">Bing</a></p>'
soup = BeautifulSoup(html, 'html.parser')

pattern = re.compile(r'(?i)(\s*(?:disponible(?:s)?|dispon[íi]vel|available)\s*(?:en|em|at)?\s*:?\s*)?(https?://[^\s<>"]+|www\.[^\s<>"]+)')

def repl(match):
    url = match.group(2)
    href = url if url.startswith('http') else 'https://' + url
    return f' <a href="{href}" target="_blank" rel="noopener">(disponible aquí)</a>'

for text_node in soup.find_all(string=True):
    if text_node.parent.name == 'a':
        continue
    new_html = pattern.sub(repl, text_node)
    if new_html != text_node:
        new_soup = BeautifulSoup(new_html, 'html.parser')
        text_node.replace_with(new_soup)

print(soup)
