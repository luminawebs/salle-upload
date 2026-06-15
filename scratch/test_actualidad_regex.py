import re

def wrap_title(html_text):
    if not html_text:
        return html_text

    # Match (YYYY). or (YYYY), followed by spaces
    # Then non-greedy match until we hit a period followed by space or <, or end of string
    def _replace_title(match):
        return f"{match.group(1)}<b>{match.group(2).strip()}</b>{match.group(3)}"

    return re.sub(
        r'(\(\d{4}\)(?:\.|,)\s*)([A-Z¿¡\[<].+?\.)(\s+|<|$)',
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
    print(wrap_title(t))
