import sys
sys.path.append(r'd:\28 Uniminuto\automatizacion_selenium_fase02')
from bs4 import BeautifulSoup
import re

def _sanitize_resource_section_html(html_text):
    if not html_text:
        return html_text

    soup = BeautifulSoup(html_text, "html.parser")
    
    # Fix nested <p> inside <li>
    for li in soup.find_all("li"):
        for p in li.find_all("p"):
            p.unwrap()

    noise_re = re.compile(
        r'^(tipo\s+de\s+actividad|tiempos|desarrollo\s+de\s+la\s+actividad|'
        r'consulta\s+de\s+materiales|recursos?|recurso\(?s?\)?\s*b[aá]sico\(?s?\)?|'
        r'recurso\(?s?\)?\s*complementario\(?s?\)?)\s*:?\s*$',
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


html = """<p>
<b>
                  Tipo de actividad
                 </b>
</p><p>
                 Colaborativa
                </p><p>
<b>
                  Tiempos
                 </b>
</p><p>
                 Desarrollo de la actividad: 1 hora
                </p><p>
                 Consulta de materiales: 2 horas
                </p><p>
<b>
                  Recursos
                 </b>
</p><p>
                 Recurso(s) básico(s):
                </p><ul>
<li>
<p>
                   ORDOÑEZ, R.
                   <i>
                    Cambio, creatividad e innovación: desafíos y respuestas.
                   </i>
                   ed. Buenos Aires, Argentina: Ediciones Granica, 2010. 285 p. Disponible en:
                   <a href="https://elibro.net/es/ereader/uniminuto/66710?page=107">
<u>
                     https://elibro.net/es/ereader/uniminuto/66710?page=107
                    </u>
</a>
</p>
</li>
</ul><p>
                 Parte II. Cap. 4 y 5.
                </p><p>
</p><ul>
<li>
<p>
                   Fernández Serrano, J. Á. (2006).
                   <i>
                    Emprende-T: ideas para nuevos emprendedores: (ed.).
                   </i>
                   Editorial Tébar Flores.
                   <a href="https://elibro.net/es/ereader/uniminuto/51920?page=1">
<u>
                     https://elibro.net/es/ereader/uniminuto/51920?page=1
                    </u>
</a>
</p>
</li>
</ul><p>
                 Cap. 2
                </p>"""

print(_sanitize_resource_section_html(html))
