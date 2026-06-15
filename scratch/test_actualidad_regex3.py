import re

def wrap_title(html_text):
    if not html_text:
        return html_text

    # Find the year marker (YYYY). or (YYYY),
    match = re.search(r'(\(\d{4}\)[.,]\s*)', html_text)
    if not match:
        return html_text

    year_marker = match.group(1)
    prefix = html_text[:match.end()]
    rest = html_text[match.end():]

    # Now we are looking at the text after the year.
    # We want to bold the "title".
    # If the title starts with an <i> or <em> tag:
    tag_match = re.match(r'^(<i[^>]*>.*?</i>|<em[^>]*>.*?</em>)', rest, flags=re.IGNORECASE)
    if tag_match:
        title = tag_match.group(1)
        suffix = rest[len(title):]
        return f"{prefix}<b>{title}</b>{suffix}"
    
    # Otherwise, the title is plain text up to the first period.
    # We'll match up to the first period.
    period_match = re.match(r'^([^.]+?\.)', rest)
    if period_match:
        title = period_match.group(1)
        suffix = rest[len(title):]
        return f"{prefix}<b>{title}</b>{suffix}"

    # Fallback: if no period is found, match up to the first comma
    comma_match = re.match(r'^([^,]+?,)', rest)
    if comma_match:
        title = comma_match.group(1)
        suffix = rest[len(title):]
        return f"{prefix}<b>{title}</b>{suffix}"

    # If all fails, don't touch
    return html_text

texts = [
    'Martín Beaumont Frañowsky. (2024). La innovación en los modelos de negocio de las empresas B de América Latina. Innovar, 34 (92)',
    'Rico, Juanita, (2026). Tendencias que definirán el 2026. <i>Revista P&M</i>',
    'Asociación Nacional de Anunciantes – ANDA, (2026), <i>Notícias</i>, Sección Violeta, Tendencias de Consumo',
    'Cristian Alejandro Rubalcava de León, Félix, M. Z., & Yesenia Sánchez Tovar. (2024). El emprendimiento social: un acercamiento a su medición dentro del contexto mexicano. <i>Innovar, 34(92)</i>'
]

for t in texts:
    print("BEFORE: ", t)
    print("AFTER : ", wrap_title(t))
    print()
