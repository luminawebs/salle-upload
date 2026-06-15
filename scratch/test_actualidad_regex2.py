import re

def wrap_title(html_text):
    if not html_text:
        return html_text

    def _replace_title(match):
        title = match.group(2).strip()
        # If the title ends with a punctuation mark, we can include it inside or outside. 
        # But for HTML, it's safer to just wrap it.
        # If the title contains HTML tags like <i>, we might want to wrap the whole thing or just the text.
        return f"{match.group(1)}<b>{title}</b>{match.group(3)}"

    # Match (YYYY). or (YYYY), followed by space
    # Then match everything until the next period followed by space/HTML tag, OR the first <i> tag.
    return re.sub(
        r'(\(\d{4}\)(?:\.|,)\s*)([A-Z¿¡\[<].+?(?:\.|\b<i>))(\s+|<|$)',
        _replace_title,
        html_text,
        flags=re.IGNORECASE
    )

texts = [
    'Martín Beaumont Frañowsky. (2024). La innovación en los modelos de negocio de las empresas B de América Latina. Innovar, 34 (92)',
    'Rico, Juanita, (2026). Tendencias que definirán el 2026. <i>Revista P&M</i>',
    'Asociación Nacional de Anunciantes – ANDA, (2026), <i>Notícias</i>, Sección Violeta, Tendencias de Consumo'
]

for t in texts:
    print("BEFORE: ", t)
    print("AFTER : ", wrap_title(t))
    print()
