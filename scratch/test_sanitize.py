import sys
sys.path.append(r'd:\28 Uniminuto\automatizacion_selenium_fase02')
from actions.foro_actions import _sanitize_resource_section_html

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
