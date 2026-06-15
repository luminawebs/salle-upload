import re
from bs4 import BeautifulSoup

def sanitize_actualidad_output(html_str):
    if not html_str or not str(html_str).strip():
        return html_str if html_str is not None else ''

    soup = BeautifulSoup(html_str, 'html.parser')

    for anchor in soup.find_all('a'):
        href = (anchor.get('href') or '').strip()
        text = anchor.get_text(strip=True)
        if not text:
            if not href:
                anchor.decompose()
            continue
            
        text_lower = text.lower()
        href_lower = href.lower() if href else ''
        
        if href_lower.startswith(('http://', 'https://')):
            if text_lower == href_lower or text_lower in href_lower or href_lower in text_lower or text_lower.startswith('http'):
                anchor.string = ''
                continue

    for text_node in soup.find_all(string=True):
        parent = text_node.parent
        if parent is not None and parent.name in ('script', 'style'):
            continue
        raw = str(text_node)
        cleaned = re.sub(r'(?i)(recurso|r)\s*\d+\s*:?\s*', '', raw)
        cleaned = re.sub(r'https?://[^\s<>")]+', '', cleaned)
        if cleaned != raw:
            text_node.replace_with(cleaned)

    for tag in soup.find_all(['p', 'li']):
        if not tag.get_text(strip=True) and not tag.find('img') and not tag.find('a', href=True):
            tag.decompose()

    return str(soup)

html1 = '<p>Recurso 1: Book. <a href="https://elibro.net/123">https://elibro.net/123</a></p>'
html2 = '<p>Article. <a href="https://google.com">[Enlace]</a></p>'
html3 = '<p>Raw url https://example.com/raw in text</p>'

print(sanitize_actualidad_output(html1))
print(sanitize_actualidad_output(html2))
print(sanitize_actualidad_output(html3))
