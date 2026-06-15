import sys
sys.path.append(r'd:\28 Uniminuto\automatizacion_selenium_fase02')
import re

def _format_book_titles(html_text):
    """Wrap common citation book titles in <b> and <i>. 
    If the source already uses italics, wrap those italics in <b>.
    Otherwise, find the title via regex and wrap it in <b><i>."""
    if not html_text:
        return html_text
        
    # If it already has <i> or <em>, wrap those in <b> (if not already bolded)
    if re.search(r'<(?:i|em)[\s>]', html_text, re.IGNORECASE):
        # We need to wrap <i>content</i> or <em>content</em> in <b>
        # Be careful not to wrap if it's already inside <b>
        def _wrap_existing_italics(match):
            tag = match.group(1)
            content = match.group(2)
            # If the user wants bold and keep italics:
            return f"<b><{tag}>{content}</{tag}></b>"
        
        # This regex might be too greedy if there are multiple <i>.
        # Let's just use a simple sub. 
        html_text = re.sub(r'<(i|em)\b[^>]*>(.*?)</\1>', _wrap_existing_italics, html_text, flags=re.IGNORECASE | re.DOTALL)
        return html_text

    def _replace_title(match):
        return f"{match.group(1)}<b><i>{match.group(2).strip()}</i></b>{match.group(3)}"

    return re.sub(
        r'(\(\d{4}\)\.\s*)([^<]+?)(\s*\(\d+(?:ª|a|er|ro|ra|º)?\s+ed\.?\))',
        _replace_title,
        html_text,
        flags=re.IGNORECASE
    )


html = """<p>
                   ORDOÑEZ, R.
                   <i>
                    Cambio, creatividad e innovación: desafíos y respuestas.
                   </i>
                   ed. Buenos Aires, Argentina: Ediciones Granica, 2010. 285 p. Disponible en:
</p>
<p>
                   Fernández Serrano, J. Á. (2006).
                   <i>Emprende-T: ideas para nuevos emprendedores: (ed.).</i>
                   Editorial Tébar Flores.
</p>
"""

print(_format_book_titles(html))
