import re
from bs4 import BeautifulSoup, Comment

# Mocking the constants and functions from actualidad_actions.py for testing
RECURSO_PREFIX_RE = re.compile(r"(?i)(recurso|r)\s*\d+\s*:?\s*")
URL_RE = re.compile(r"https?://[^\s<>\")]+")

def sanitize_actualidad_output(html_str):
    if not html_str or not str(html_str).strip():
        return html_str if html_str is not None else ""

    soup = BeautifulSoup(html_str, "html.parser")

    for anchor in soup.find_all("a"):
        href = (anchor.get("href") or "").strip()
        text = anchor.get_text(strip=True)
        if not text:
            anchor.decompose()
            continue
        text_lower = text.lower()
        href_lower = href.lower() if href else ""
        if href_lower.startswith(("http://", "https://")):
            if text_lower == href_lower or text_lower in href_lower or href_lower in text_lower:
                anchor.decompose()
                continue
            if text_lower.startswith("http://") or text_lower.startswith("https://"):
                anchor.decompose()
                continue
        anchor.unwrap()

    for text_node in soup.find_all(string=True):
        if isinstance(text_node, Comment):
            continue
        parent = text_node.parent
        if parent is not None and parent.name in ("script", "style"):
            continue
        raw = str(text_node)
        cleaned = RECURSO_PREFIX_RE.sub("", raw)
        cleaned = URL_RE.sub("", cleaned)
        if cleaned != raw:
            text_node.replace_with(cleaned)

    for tag in soup.find_all(["p", "li"]):
        if not tag.get_text(strip=True) and not tag.find("img"):
            tag.decompose()

    return str(soup)

# Test cases
test_html = """
<div>
    <p>Recurso 1: Este es el primer recurso.</p>
    <p>R2: Este es el segundo recurso.</p>
    <p>r3 Este es el tercer recurso.</p>
    <p>RECURSO 4 Este es el cuarto recurso.</p>
    <p><a href="https://example.com">https://example.com</a></p>
    <p>Visite R1: para más info.</p>
</div>
"""

print("Original HTML:")
print(test_html)
print("\nSanitized HTML:")
print(sanitize_actualidad_output(test_html))
