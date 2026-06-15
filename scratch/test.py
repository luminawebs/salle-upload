import sys
sys.path.append(r'd:\28 Uniminuto\automatizacion_selenium_fase02')
from actions.foro_actions import _hide_plain_urls_in_html, _convert_lists_to_paragraphs

html = """<ul>
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
</ul>"""
hidden = _hide_plain_urls_in_html(html)
print('Hidden:', repr(hidden))
conv = _convert_lists_to_paragraphs(hidden)
print('Converted:', repr(conv))
