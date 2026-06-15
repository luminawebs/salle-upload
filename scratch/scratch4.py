from bs4 import BeautifulSoup

html = """<div class="card-d403">
    <div class="c-d403-1"><em><span class="fa fa-mouse-pointer txt-v-blue"></span></em></div>
    <div class="c-d403-2">
        <p>Gerencie. (2023, septiembre 4). <em>¿Cómo reconocer un activo bajo NIIF?</em></p>
        <p>Ingrese <a
                href="https://www.gerencie.com/nifi-para-principiantes-como-reconocer-un-activo-bajo-nifi-parte-ii.html"
                target="_blank" rel="noreferrer noopener">Aquí</a></p>
    </div>
</div>"""

soup = BeautifulSoup(html, "html.parser")
container = soup.find('div', class_='c-d403-2')
if container:
    paragraphs = container.find_all('p')
    if len(paragraphs) >= 2:
        paragraphs[0].string = "New citation text"
        a_tag = paragraphs[1].find('a')
        if a_tag:
            a_tag['href'] = "https://new.url"

print(str(soup))
