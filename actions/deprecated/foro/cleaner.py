import re
from bs4 import BeautifulSoup
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from html_generator.generate_html import clean_html

URL_PATTERN = re.compile(r'https?://[^\s<>"\']+', re.IGNORECASE)

def clean_foro_html(raw_html):
    """
    Cleans the raw HTML using the existing generate_html.clean_html approach,
    and strips meaningless tags.
    """
    if not raw_html:
        return ""
        
    soup = BeautifulSoup(raw_html, "html.parser")
    
    # Remove any depositphotos images just in case, though they usually aren't in Foros
    for tag in soup.find_all(True):
        if tag.has_attr('src') and 'depositphotos.com' in tag['src']:
            tag.extract()
        elif tag.has_attr('href') and 'depositphotos.com' in tag['href']:
            tag.extract()
            
    # Clean up inline styles, classes, and spans
    for tag in soup.find_all(True):
        if tag.name in ['span', 'font', 'div']:
            tag.unwrap()
        else:
            # Keep only essential attributes
            attrs = dict(tag.attrs)
            tag.attrs = {}
            if tag.name == 'a' and 'href' in attrs:
                tag['href'] = attrs['href']
            if tag.name == 'img' and 'src' in attrs:
                tag['src'] = attrs['src']
                if 'alt' in attrs:
                    tag['alt'] = attrs['alt']
            
    cleaned_soup_str = str(soup)
    return clean_html(cleaned_soup_str)

def _sanitize_resource_section_html(html_text):
    """
    Remove repeated 'Tipo de actividad/Tiempos/Consulta...' noise captured from malformed source.
    """
    if not html_text:
        return html_text

    soup = BeautifulSoup(html_text, "html.parser")
    
    # Fix nested <p> inside <li> to avoid deduplication bug where <p> text matches <li> text
    for li in soup.find_all("li"):
        for p in li.find_all("p"):
            p.unwrap()

    noise_re = re.compile(
        r'^(tipo\s+de\s+actividad.*|colaborativa|tiempos.*|desarrollo\s+de\s+la\s+actividad.*|'
        r'consulta\s+de\s+materiales.*|recursos?|recurso\(?s?\)?\s*b[aá]sico\(?s?\)?.*|'
        r'recurso\(?s?\)?\s*complementario\(?s?\)?.*)\s*$',
        re.IGNORECASE,
    )

    seen = set()
    for tag in soup.find_all(["p", "li", "div"]):
        text = " ".join(tag.get_text(" ", strip=True).split())
        if not text:
            tag.decompose()
            continue
        if noise_re.match(text):
            tag.decompose()
            continue
        dedupe_key = text.lower()
        if dedupe_key in seen:
            tag.decompose()
            continue
        seen.add(dedupe_key)

    return str(soup).strip() or None

def _wrap_book_title_in_italics(html_text):
    """Wrap common citation book titles in <b><i> when the source does not already use italics.
    If the source already uses italics, wrap those italics in <b>."""
    if not html_text:
        return html_text
        
    if re.search(r'<(?:i|em)[\s>]', html_text, re.IGNORECASE):
        def _wrap_existing_italics(match):
            tag = match.group(1)
            content = match.group(2)
            return f"<b><{tag}>{content}</{tag}></b>"
        
        return re.sub(r'<(i|em)\b[^>]*>(.*?)</\1>', _wrap_existing_italics, html_text, flags=re.IGNORECASE | re.DOTALL)

    def _replace_title(match):
        return f"{match.group(1)}<b><i>{match.group(2).strip()}</i></b>{match.group(3)}"

    return re.sub(
        r'(\(\d{4}\)\.\s*)([^<]+?)(\s*\(\d+(?:ª|a|er|ro|ra|º)?\s+ed\.?\))',
        _replace_title,
        html_text,
        flags=re.IGNORECASE
    )

def _hide_plain_urls_in_html(html_text):
    """Remove all URL links completely from resource HTML - no visible links or 'Enlace' text."""
    if not html_text:
        return html_text

    soup = BeautifulSoup(html_text, "html.parser")

    # Remove all <a> tags completely (but keep their text)
    for a in soup.find_all("a"):
        a.unwrap()  # This removes the tag but keeps its contents

    # Remove all <u> tags completely (but keep their text)
    for u in soup.find_all("u"):
        u.unwrap()
    
    # Also remove any standalone URLs that are not in <a> tags
    for text_node in soup.find_all(string=True):
        if text_node.parent and text_node.parent.name == "a":
            continue  # Skip as these will be removed by decompose anyway (though we unwrapped them)
        text = str(text_node)
        # Remove URLs from plain text (replace with empty string)
        cleaned_text = URL_PATTERN.sub('', text)
        
        # Clean up spaces before punctuation
        cleaned_text = re.sub(r'\s+([.,;:?])', r'\1', cleaned_text)
        
        if cleaned_text != text:
            text_node.replace_with(cleaned_text)
    
    # Clean up any empty <p> tags that might have been left
    for p in soup.find_all("p"):
        if not p.get_text(strip=True):
            p.decompose()
    
    # Clean up multiple consecutive spaces or empty lines
    final_html = str(soup)
    final_html = re.sub(r'\n\s*\n', '\n', final_html)
    final_html = re.sub(r'  +', ' ', final_html)
    
    return final_html

def _convert_lists_to_paragraphs(html_text):
    """Convert <ul>/<ol>/<li> elements to plain paragraphs without nested structures."""
    if not html_text:
        return html_text
    
    soup = BeautifulSoup(html_text, "html.parser")
    
    # First, remove any <p> inside <li>
    for li in soup.find_all("li"):
        for p in li.find_all("p"):
            p.unwrap()
    
    # Then replace each <li> with a <p> containing the same content
    for li in soup.find_all("li"):
        p = soup.new_tag("p")
        # Move all contents from li to p
        for child in list(li.children):
            if isinstance(child, str):
                p.append(child)
            else:
                p.append(child.extract())
        li.replace_with(p)
    
    # Unwrap ul and ol tags to flatten the structure
    for ul_ol in soup.find_all(["ul", "ol"]):
        ul_ol.unwrap()
    
    # Remove any empty paragraphs
    for p in soup.find_all("p"):
        if not p.get_text(strip=True):
            p.decompose()
    
    return str(soup)
