import re

refs = [
    "Recurso 1: Rosa Huamaní. (2020, junio 18). La evolución histórica del comercio internacional [Video]. YouTube. https://www.youtube.com/watch?v=vyCxXrGyvEo",
    "Economia Internacional. (2025, septiembre 9). Principales teorías del comercio internacional [Video]. YouTube. https://www.youtube.com/watch?v=KEprCzriKZU",
    "Villalobos Torres, L. R. (2006). Fundamentos de comercio internacional (ed.). Editorial Miguel Ángel Porrúa. (pp. 10–32; 92–124). https://elibro.net/es/lc/uniminuto/titulos/75329",
    "Sosa Carpenter, R. (2014). Principios y fundamentos del comercio global internacional (ed.). Delta Publicaciones. (pp. 25–27). https://elibro.net/es/ereader/uniminuto/170065",
    "Jaime Saldarriaga-Romero, V., Muñoz Molina, Y., & Velásquez Ceballos, H. (2024). Brand performance development : Synthesis and research agenda. Revista Lasallista de Investigación, 21 (1). https://doi.org/10.22507/rli.v21n1a3"
]

def extract_title(text):
    text = re.sub(r'(?i)^(Recurso\s*\d+:\s*)', '', text).strip()
    
    # Try to find the date part: (YYYY, ...) or (YYYY).
    # The title comes right after it.
    match = re.search(r'\(\d{4}[^\)]*\)\.\s*(.+?)(?:\s*\[|\s*\(ed\.\)|\.\s*[A-Z]|\.\s*$)', text)
    if match:
        title = match.group(1).strip()
        # Clean trailing dots
        if title.endswith('.'): title = title[:-1]
        return title
    return "Not found"

for r in refs:
    print(f"Ref: {r}")
    print(f"Title: {extract_title(r)}\n")
